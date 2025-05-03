Smart Order Router — Based on Cont & Kukanov’s Static Model

This project is a development of the Cont & Kukanov Smart Order Router, following their static cost model for Optimal Order Placement in Limit Order Markets.

The idea behind this router is to split a 5,000-share buy order across multiple venues using three key risk parameters:
	•	lambda_under
	•	lambda_over
	•	theta_queue

⸻

Thought Process

A brief overview of the logic implemented in backtest.py and how the final solution came together.

The project centered around building two main functions to simulate the allocation and cost behavior outlined in the provided pseudocode. Since the allocate function calculates optimal splits in a static setting, we needed to develop a sequential simulation that could reflect how these allocations would perform over real timestamped market snapshots.

This led to the creation of a simulation function that:
	1.	Iterates through real L1 quote snapshots over time.
	2.	Uses the static allocator to compute a split at each step.
	3.	Accumulates the actual cost incurred given available liquidity and venue conditions.

We chose Grid Search over Random Search to explore all possible combinations of the three parameters (lambda_under, lambda_over, theta_queue) in a fully exhaustive manner. Given that even small savings in basis points can translate into significant cost reductions on large trading volumes, this choice allowed us to rigorously test 10 values per parameter — ensuring high granularity in our optimization.

⸻

Function Descriptions
	•	class Venues
The Venues class was built to represent each venue as an object containing the relevant attributes: ask price, ask size, fee, and rebate — as expected by the pseudocode, which required handling multiple venues simultaneously.
	•	compute_cost() (from pseudocode)
This function implements the cost model outlined in Section 2.3 of the paper. It computes the cost of a given split based on venue quotes, trading fees, rebates, and penalties (underfill, overfill, queue risk).
	•	allocate() (from pseudocode)
The static allocator function. It computes the optimal way to split a trade across multiple venues using the cost model above. It tries all valid combinations (in steps of 100 shares) and selects the one with the lowest expected cost.
	•	GridSearchCV()
This custom grid search function exhaustively evaluates all combinations of input parameters to identify the configuration that minimizes actual execution cost during the simulation.
	•	simulate_trading()
This is the core simulation engine. At each timestamp, it uses allocate() to compute an optimal split of the remaining order, executes as much as possible based on venue constraints, and tracks actual execution costs. It returns total and average cost, allowing comparison with benchmark strategies.

⸻

Comparative Methods

In addition to the optimal strategy, we implemented the three baseline methods specified in the instructions:
	•	Best Ask
A simple greedy strategy that routes all available volume to the venue with the lowest current ask price. While aggressive, it ignores execution risk and liquidity fragmentation.
	•	VWAP (Volume-Weighted Average Price)
Allocates shares across venues proportionally to their displayed liquidity. Larger venues receive more volume. This strategy mimics market participation but does not prioritize best price.
	•	TWAP (Time-Weighted Average Price)
Splits the total order evenly across 60-second time intervals. Within each time bucket, it allocates to the best-priced venues first, aiming for smooth, time-distributed execution.

⸻

Limitations & Use of AI

As someone unfamiliar with trading data, I encountered challenges understanding and differentiating some key market concepts. That said, within the time constraints of the project, I incorporated AI support to a basic extent to accelerate development and clarify parts of the modeling process.

Examples where AI provided useful guidance:
	•	Replacing inefficient nested loops in GridSearchCV with the itertools.product pattern for combinatorial searches.
	•	Clarifying the purpose and structure of TWAP and VWAP strategies, which I had not encountered before this assignment.