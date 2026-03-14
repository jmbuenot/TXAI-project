# Model Evaluation

## Baseline (global mean) — validation set

- RMSE: 0.6329
- MAE:  0.3641
- R²:   -0.0001

## Initial XGBoost model — validation set

- RMSE: 0.3567
- MAE:  0.2569
- R²:   0.6823

## Tuned XGBoost model — validation set

- RMSE: 0.3567
- MAE:  0.2569
- R²:   0.6823

Best tuned hyperparameters:

- max_depth: 6
- learning_rate: 0.05
- n_estimators: 500

## Tuned XGBoost model — test set

- RMSE: 0.3556
- MAE:  0.2557
- R²:   0.6548
