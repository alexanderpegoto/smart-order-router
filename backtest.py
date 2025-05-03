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


def simulate_trading(snapshots, lambda_o, lambda_u, theta_queue, order_target=5000):
    """
    Simulate trading across snapshots using allocator + cost model.

    Inputs:
        - snapshots: list of snapshots, each is a list of Venue objects
        - order_target: total number of shares to buy (e.g. 5000)
        - lambda_o, lambda_u, theta_queue: parameters to test

    Returns:
        - total_cost: total cost to execute the trade
    """
    remaining = order_target
    total_cost = 0

    for snapshot in snapshots:
        # Decide how to split the remaining order
        split, expected_cost = allocate(remaining, snapshot, lambda_o, lambda_u, theta_queue)
        # execution
        executed = 0
        actual_cost = 0
        for i, venue in enumerate(snapshot):
            # we want to execute whichever is smallest
            execute = min(split[i], venue.ask_size)
            executed += execute
            # Adding the cummulative cost inccured
            cost = execute * (venue.ask + venue.fee)
            # calculating rebate to calculate final cost
            rebate = max(split[i] - execute, 0) * venue.rebate
            actual_cost += cost - rebate

        underfill = max(remaining - executed, 0)
        overfill = max(executed - remaining, 0)
        risk_penalty = theta_queue * (underfill + overfill)
        cost_penalty = lambda_u * underfill + lambda_o * overfill

        total_cost += actual_cost + risk_penalty + cost_penalty
        remaining -= executed

    return total_cost











# if __name__ == "__main__":
    
    
    


