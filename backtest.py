import pandas as pd
import numpy as np
from dataclasses import dataclass
import itertools
import json


@dataclass
class Venues:
    venue_id: int
    ask: float
    ask_size: float
    fee: float = 0.003
    rebate: float =0.002
        

#Cost Function
def compute_cost(split, venues,order_size, lambda_o, lambda_u, theta_queue):
    """function that computes the total cost of a given split allocation
    based on venue and penalies incurred"""
    executed = 0
    cash_spent = 0
    for i in range(0,len(venues)):
        exe = min(split[i], venues[i].ask)
        executed += exe
        cash_spent += exe * (venues[i].ask + venues[i].fee)
        maker_rebate = max(split[i]-exe, 0) * venues[i].rebate
        cash_spent -= maker_rebate
    
    underfill = max(order_size-executed,0)
    overfill = max(executed - order_size, 0)
    risk_pen = theta_queue * (underfill + overfill)
    cost_pen = lambda_u * underfill + lambda_o * overfill
    
    return cash_spent + risk_pen + cost_pen


def allocate(order_size, venues, lambda_o, lambda_u, theta_queue):
    
    """Static allocator based on model"""
    
    step = 100
    splits = [[]]
    
    for v in range(len(venues)):
        new_split = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min((order_size-used), venues[v].ask_size)
            for q in range(0, max_v + step, step):
                new_split.append(alloc +[q])
        splits = new_split
    
    best_cost = float("inf")
    best_split = []
    
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues,order_size, lambda_o, lambda_u, theta_queue)
        
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
            
    return best_split, best_cost

def GridSearchCV(model, param_grid, sorted_snapshots):
    """
    Function doing exhaustive search over specified parameter values
    for all combinations of parameters lambda and theta.
    
    Parameters:
    -----
    model: function
        Model function that needs to be passed into the grid search to test
        all possible combinations
    param_grid: dict
        Dictionary with a list of values for all parameters
        
    Returns:
    -----
    best_params: dict
        Dictionary with the best parameter values
    best_score: float
        Score achieved with the best parameters
    """
    
    param_names = ['lambda_o', 'lambda_u', 'theta_queue']
    param_values = [param_grid[name] for name in param_names]

    best_score = float("inf")
    best_params = None
    
    for combination in itertools.product(*param_values):
        lambda_o, lambda_u, theta_queue = combination
        
        # In your current function, score is expected to be total_cost
        result = model(lambda_o, lambda_u, theta_queue, sorted_snapshots)
        score = result['total_cost']
        
        if score < best_score:
            best_score = score
            best_result = result
    
    return best_result



def simulate_trading(lambda_o, lambda_u, theta_queue, snapshots, order_target=5000):
    """
    Simulate trading across snapshots using allocator + cost model.

    Inputs:
        - snapshots: list of snapshots grouped by timestamp venue 
        - order_target: total number of shares to buy (e.g. 5000)
        - lambda_o, lambda_u, theta_queue: parameters to test

    Returns:
        - Dict: execution results
    """
    remaining = order_target
    total_cost = 0
    executed_total = 0
    execution_detail = []

    for ts, venues in snapshots:
        if remaining <= 0:
            break
        # Decide how to split the remaining order
        split, expected_cost = allocate(remaining, venues, lambda_o, lambda_u, theta_queue)
        # execution
        snapshot_executed = 0
        snapshot_cost = 0
        for i, shares in enumerate(split):
            # we want to execute whichever is smallest
            execute = min(shares, venues[i].ask_size)
            snapshot_executed += execute
            # Adding the cumulative cost incurred
            share_cost = (execute * venues[i].ask) + (execute * venues[i].fee)
            snapshot_cost += share_cost
            
            execution_detail.append({
                'timestamp': ts,
                'venue_id': venues[i].venue_id,
                'shares': execute,
                'price': venues[i].ask,
                'cost': share_cost
            })

        executed_total += snapshot_executed
        total_cost += snapshot_cost
        remaining -= snapshot_executed
    
    # Calculate average price
    avg_price = total_cost / executed_total if executed_total > 0 else 0
    
    return {
        'params': (lambda_o, lambda_u, theta_queue),
        'executed_shares': executed_total,
        'total_cost': total_cost,
        'avg_price': avg_price
    }

############
# Comparative Strategies #
#############


# Baseline strategy: Best Ask
def best_ask_strategy(sorted_snapshots, order_target=5000):
    """Always take liquidity from the venue with the best price"""
    remaining = order_target
    total_cost = 0
    executed_total = 0
    
    for ts, venues in sorted_snapshots:
        if remaining <= 0:
            break
            
        # Sort venues by ask price (lowest first)
        sorted_venues = sorted(venues, key=lambda v: v.ask)
        
        for venue in sorted_venues:
            # Execute as much as possible at this venue
            execute = min(remaining, venue.ask_size)
            
            if execute > 0:
                # Calculate costs
                execution_cost = execute * venue.ask + execute * venue.fee
                
                executed_total += execute
                total_cost += execution_cost
                remaining -= execute
                
                # If we've filled the order, stop
                if remaining <= 0:
                    break
    
    # Calculate average price
    avg_price = total_cost / executed_total if executed_total > 0 else 0
    
    return {
        'strategy': 'best-ask',
        'executed_shares': executed_total,
        'total_cost': total_cost,
        'avg_price': avg_price
    }
    
def vwap_strategy(sorted_snapshots, order_target=5000):
    """
    Implement a VWAP strategy that weights prices by displayed ask size.
    """
    remaining = order_target
    total_cost = 0
    executed_total = 0
    
    for ts, venues in sorted_snapshots:
        if remaining <= 0:
            break
        
        # Calculate total available volume across all venues
        total_volume = sum(venue.ask_size for venue in venues)
        
        if total_volume <= 0:
            continue
        
        # Allocate shares based on volume weight
        allocations = []
        for venue in venues:
            # Weight by venue's ask size relative to total available
            weight = venue.ask_size / total_volume
            # Allocate shares proportionally
            shares = min(remaining * weight, venue.ask_size)
            allocations.append((venue, shares))
        
        # Execute allocations
        snapshot_executed = 0
        snapshot_cost = 0
        
        for venue, shares in allocations:
            execute = min(int(shares), venue.ask_size) 
            
            if execute > 0:
                # Calculate costs
                share_cost = execute * venue.ask
                fee_cost = execute * venue.fee
                
                snapshot_executed += execute
                snapshot_cost += share_cost + fee_cost
        
        executed_total += snapshot_executed
        total_cost += snapshot_cost
        remaining -= snapshot_executed
    
    # Calculate average price
    avg_price = total_cost / executed_total if executed_total > 0 else 0
    
    return {
        'strategy': 'vwap',
        'executed_shares': executed_total,
        'total_cost': total_cost,
        'avg_price': avg_price
    }

def twap_strategy(sorted_snapshots, order_target=5000):
    """
    Implement a 60-second-bucket TWAP strategy.
    Splits the order evenly across 60-second time buckets.
    """
    remaining = order_target
    total_cost = 0
    executed_total = 0
    
    # Get timestamps and convert to seconds for bucketing
    timestamps = [ts for ts, _ in sorted_snapshots]
    if not timestamps:
        return {
            'strategy': 'twap',
            'executed_shares': 0,
            'total_cost': 0,
            'avg_price': 0
        }
    
    start_time = pd.to_datetime(timestamps[0])
    end_time = pd.to_datetime(timestamps[-1])
    total_seconds = (end_time - start_time).total_seconds()
    
    # Calculate number of 60-second buckets
    num_buckets = max(1, int(total_seconds / 60))
    shares_per_bucket = order_target / num_buckets
    
    # Create time buckets
    current_bucket_end = start_time + pd.Timedelta(seconds=60)
    bucket_shares_remaining = shares_per_bucket
    
    # Process each snapshot
    for ts, venues in sorted_snapshots:
        ts_datetime = pd.to_datetime(ts)
        
        # Check if we've moved to a new bucket
        while ts_datetime > current_bucket_end and remaining > 0:
            # Move to next bucket
            current_bucket_end += pd.Timedelta(seconds=60)
            bucket_shares_remaining = shares_per_bucket
        

        if bucket_shares_remaining <= 0:
            continue
        
        # Calculate how many shares to execute in this snapshot
        shares_to_execute = min(bucket_shares_remaining, remaining)
        
        # Sort venues by best price
        sorted_venues = sorted(venues, key=lambda v: v.ask)
    
        snapshot_executed = 0
        for venue in sorted_venues:
            execute = min(shares_to_execute - snapshot_executed, venue.ask_size)
            
            if execute > 0:
                execution_cost = execute * venue.ask + execute * venue.fee
                snapshot_executed += execute
                total_cost += execution_cost
                

                if snapshot_executed >= shares_to_execute:
                    break
        
        # Update remaining shares
        executed_total += snapshot_executed
        remaining -= snapshot_executed
        bucket_shares_remaining -= snapshot_executed
        
        # If order is complete, stop
        if remaining <= 0:
            break
    
    # Calculate average price
    avg_price = total_cost / executed_total if executed_total > 0 else 0
    
    return {
        'strategy': 'twap',
        'executed_shares': executed_total,
        'total_cost': total_cost,
        'avg_price': avg_price
    }
    
####################
####################
####################

if __name__ == "__main__":
    # Load data
    l1 = pd.read_csv('l1_day.csv')
    
    # Group by timestamp and publisher_id to get first message per venue per timestamp
    grouped = l1.groupby(['ts_event', 'publisher_id']).first().reset_index()
    
    # Create snapshots dictionary
    snapshots = {}
    for ts, group in grouped.groupby('ts_event'):
        venues_at_ts = []
        for _, row in group.iterrows():                
            venue = Venues(
                venue_id=row['publisher_id'],
                ask=row['ask_px_00'],
                ask_size=row['ask_sz_00'],
                fee=0.003,
                rebate=0.002
            )
            venues_at_ts.append(venue)
            snapshots[ts] = venues_at_ts
    
    # Convert to sorted list of (timestamp, venues) tuples for sequential processing
    sorted_snapshots = sorted(snapshots.items())
    
    # Define parameter grid
    param_grid = {
    'lambda_o': list(np.arange(0.05, 0.15, 0.01)),
    'lambda_u': list(np.arange(0.05, 0.15, 0.01)),
    'theta_queue': list(np.arange(0.0001, 0.001, 0.0001))
    }
    
    best_result = GridSearchCV(simulate_trading, param_grid, sorted_snapshots)
    best_ask_result = best_ask_strategy(sorted_snapshots)
    twap_result = twap_strategy(sorted_snapshots)
    vwap_result = vwap_strategy(sorted_snapshots)
    
    # Calculate savings in basis points
    best_avg_price = best_result['avg_price']
    best_ask_avg_price = best_ask_result['avg_price']
    
    # Calculate savings in basis points
    best_avg_price = best_result['avg_price']
    best_ask_avg_price = best_ask_result['avg_price']
    twap_avg_price = twap_result['avg_price']
    vwap_avg_price = vwap_result['avg_price']
    
    savings_vs_best_ask = (best_ask_avg_price - best_avg_price) / best_ask_avg_price * 10000
    savings_vs_twap = (twap_avg_price - best_avg_price) / twap_avg_price * 10000
    savings_vs_vwap = (vwap_avg_price - best_avg_price) / vwap_avg_price * 10000
    
    # Format results as JSON
    results = {
        "best_parameters": {
            "lambda_over": best_result['params'][0],
            "lambda_under": best_result['params'][1],
            "theta_queue": best_result['params'][2]
        },
        "our_model": {
            "total_cost": best_result['total_cost'],
            "avg_price": best_result['avg_price']
        },
        "best_ask": {
            "total_cost": best_ask_result['total_cost'],
            "avg_price": best_ask_result['avg_price']
        },
        "twap": {
            "total_cost": twap_result['total_cost'],
            "avg_price": twap_result['avg_price']
        },
        "vwap": {
            "total_cost": vwap_result['total_cost'],
            "avg_price": vwap_result['avg_price']
        },
        "savings_bps": {
            "vs_best_ask": savings_vs_best_ask,
            "vs_twap": savings_vs_twap,
            "vs_vwap": savings_vs_vwap
        }
    }

    # Print results as JSON
    print(json.dumps(results, indent=2, sort_keys=False))
    
    with open("output_test.json", "w") as f:
        json.dump(results, f, indent=2, sort_keys=False)
    
    
    
    


