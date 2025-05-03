import pandas as pd
import numpy as np
from dataclasses import dataclass

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

def GridSearchCV(model, param_grid, ):
    """Function doing exhaustive search over specified parameters values 
        for all combinations of parameters lambda and theta.
        
        Parameters:
        -----
        model: function
            model of function that needs to be pass into the grid search to test
            all possible combinations
        param_grid: dict
            dictionary with a list of values of all parameters
            
        Returns:
        -----
        best_params
        best_score
            
    """
    
    lambda_over_list = list(param_grid['lambda_o'])
    lambda_under_list = list(param_grid['lambda_u'])
    theta_queue_list = list(param_grid['theta_queue'])

    best_score = float("inf")
    best_params = None
    
        
    for lambda_over in lambda_over_list:
        for lambda_under in lambda_under_list:
            for theta_queue in theta_queue_list:
                score = model(lambda_over, lambda_under, theta_queue)
                
                if score < best_score:
                    best_score = score
                    best_params = {
                        'lambda_over': lambda_over,
                        'lambda_under': lambda_under,
                        'theta_queue': theta_queue
                    }
    return best_params, best_score


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
        'avg_price': avg_price,
        'details': execution_detail
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
        'lambda_o': [l for l in range(0.05,0.15,0.01)],
        'lambda_u': [l for l in range(0.05,0.15,0.01)],
        'theta_queue': [l for l in range(0.0001,0.001,0.0001)]
    }
    
    # Run grid search to find optimal parameters
    best_result = GridSearchCV(simulate_trading, param_grid, sorted_snapshots)
    
    # Run baseline strategies
    best_ask_result = best_ask_strategy(sorted_snapshots)
    
    # TODO: Implement TWAP and VWAP strategies
    
    # Calculate savings in basis points
    best_avg_price = best_result['avg_price']
    best_ask_avg_price = best_ask_result['avg_price']
    
    

    
    


