import sys
import numpy as np
import pandas as pd
import sympy as sp
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
import feyn

def get_symbolic_model(expr):
    """takes string as input and
    outputs a SymPy equation"""
    feature_names = ['Z', 'ZDR', 'KDP', 'RhoHV']
    local_dict = {f:sp.Symbol(f) for f in feature_names}
    sp_model = sp.parse_expr(expr, local_dict=local_dict)
    return sp_model

def get_simplicity(sp_model):
    """takes SymPy equation as input and
    outputs a score representing the equation's simplicity"""
    # compute numumber of components
    num_components = 0
    for _ in sp.preorder_traversal(sp_model):
        num_components += 1

    # compute simplicity as per srbench criteria by La Cava et al. (2021)
    simplicity = -np.round(np.log(num_components)/np.log(5), 1)
    return simplicity

def run_feyn_1group(df_group, variable):
    """Run Feyn model on one rain type,
    returning a Pandas DataFrame with the metrics and equations for 10 iterations"""

    # create lists of each model accuracy measurement
    train_r2 = []
    test_r2 = []
    all_r2 = []
    train_rmse = []
    test_rmse = []
    train_nrmse = []
    test_nrmse = []
    all_nrmse = []
    equations = []
    simplicity = []

    # run 10 iterations
    for i in range(10):

        print(f"Iteration {i} for {variable}")

        # split data into train and test, with seed being the iteration of the for loop
        train_df, test_df = train_test_split(df_group, test_size=0.25, random_state=i)

        ql = feyn.QLattice(random_seed=1)

        # fit and train model
        models = ql.auto_run(
            data=train_df,
            output_name='gauge_precipitation_matched',
            )

        # get best model
        best_model = models[0]

        # calculate train and test r2 and  append to list
        train_pred = best_model.predict(train_df)
        test_pred = best_model.predict(test_df)
        all_pred = best_model.predict(df_group)

        train_r2.append(r2_score(train_df['gauge_precipitation_matched'], train_pred))
        test_r2.append(r2_score(test_df['gauge_precipitation_matched'], test_pred))
        all_r2.append(r2_score(df_group['gauge_precipitation_matched'], all_pred))

        # calculate test and train rmse
        rmse_train = np.sqrt(mean_squared_error(train_df['gauge_precipitation_matched'], train_pred))
        train_rmse.append(rmse_train)
        rmse_test = (np.sqrt(mean_squared_error(test_df['gauge_precipitation_matched'], test_pred)))
        test_rmse.append(rmse_test)
        rmse_all = np.sqrt(mean_squared_error(df_group['gauge_precipitation_matched'], all_pred))

        # normalize rmse with mean of y values
        train_nrmse.append(rmse_train / train_df['gauge_precipitation_matched'].mean())
        test_nrmse.append(rmse_test / test_df['gauge_precipitation_matched'].mean())
        all_nrmse.append(rmse_all / df_group['gauge_precipitation_matched'].mean())

        # get best equation as string
        expr_str = str(best_model.sympify())

        # convert equation to SymPy, append to list
        expr_sp = get_symbolic_model(expr_str)
        equations.append(expr_sp)

        # append simplicity score to list
        expr_simplicity = get_simplicity(expr_sp)
        simplicity.append(expr_simplicity)

    metrics = {
        f'{variable}_train_r2': train_r2,
        f'{variable}_test_r2': test_r2,
        f'{variable}_all_r2': all_r2,
        f'{variable}_train_rmse': train_rmse,
        f'{variable}_test_rmse': test_rmse,
        f'{variable}_train_nrmse': train_nrmse,
        f'{variable}_test_nrmse': test_nrmse,
        f'{variable}_all_nrmse': all_nrmse,
        f'{variable}_equation': equations,
        f'{variable}_simplicity': simplicity,
    }

    output = pd.DataFrame(metrics)

    return output

def run_feyn_all_groups(df, radar):
    df_feyn = df[['Reflectivity', 'Zdr', 'Kdp', 'Rhohv', 'gauge_precipitation_matched']] \
                .rename(columns={'Reflectivity': 'Z', 'Zdr': 'ZDR', 'Kdp': 'KDP', 'Rhohv': 'RhoHV'})

    above_mean = df_feyn[df_feyn[radar] >= df_feyn[radar].mean()]
    below_mean = df_feyn[df_feyn[radar] < df_feyn[radar].mean()]

    above_metrics = run_feyn_1group(above_mean, f'a_{radar}')
    below_metrics = run_feyn_1group(below_mean, f'b_{radar}')

    # combine metrics for above and below the mean of the radar variable into one DataFrame
    metrics = pd.concat([above_metrics, below_metrics], axis=1)

    # compute mean metrics
    metrics['mean_train_r2'] = metrics[[f'a_{radar}_train_r2', f'b_{radar}_train_r2']].mean(axis=1)
    metrics['mean_test_r2'] = metrics[[f'a_{radar}_test_r2', f'b_{radar}_test_r2']].mean(axis=1)
    metrics['mean_train_rmse'] = metrics[[f'a_{radar}_train_rmse', f'b_{radar}_train_rmse']].mean(axis=1)
    metrics['mean_test_rmse'] = metrics[[f'a_{radar}_test_rmse', f'b_{radar}_test_rmse']].mean(axis=1)
    metrics['mean_train_nrmse'] = metrics[[f'a_{radar}_train_nrmse', f'b_{radar}_train_nrmse']].mean(axis=1)
    metrics['mean_test_nrmse'] = metrics[[f'a_{radar}_test_nrmse', f'b_{radar}_test_nrmse']].mean(axis=1)
    metrics['mean_simplicity'] = metrics[[f'a_{radar}_simplicity', f'b_{radar}_simplicity']].mean(axis=1)

    return metrics

if __name__ == "__main__":

    df = pd.read_csv("dataset.csv")

    radar = sys.argv[1]

    metrics = run_feyn_all_groups(df, radar)
    metrics.to_csv(f"subset_metrics_feyn_{radar}_mean.csv")