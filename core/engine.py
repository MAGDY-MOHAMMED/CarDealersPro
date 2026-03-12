    import pandas as pd 
    import gc
    import numpy as np
    from joblib import Parallel, delayed
    from utils.logger import setup_logger
    from typing import  Tuple, Dict


    logger= setup_logger (__name__)
    class DataOptimizer :
        def __init__(self,n_jobs=-1, category_threshold :float=0.5 ):
            self.n_jobs=n_jobs
            self.category_threshold= category_threshold
            logger.info(f"Engine Ready : Cores {n_jobs} , Thresholds = {category_threshold}")
        def _optimize_single_column(self,col_name : str ,col_series : pd.Series) -> Tuple [str,pd.Series] :
            if col_series.isnull().all() :
                return col_name,col_series
            col_type= col_series.dtype
            if np.issubdtype (col_type, np.number) :

                target = 'integer' if np.issubdtype(col_type, np.integer) else 'float'
                optimized_col = pd.to_numeric(col_series,downcast=target)
                return col_name, optimized_col
            if col_type== object:
                num_unique= col_series.nunique(dropna=True)
                num_total= col_series.shape[0]
                if (num_unique / num_total) < self.category_threshold  :
                    return col_name, col_series.astype('category')
            return col_name, col_series
        

        def optimize (self, df : pd.DataFrame, n_jobs : int = -1 ) ->  pd.DataFrame :
            initial_mem = df.memory_usage(deep=True).sum() / 1024**2

            logger.info(f"Starting Optimization : inittial size { initial_mem:.2f}MB")

            numeric_cols= df.select_dtypes(include=[np.number]).columns

            stats_before= df[numeric_cols].describe() if not numeric_cols.empty else None

            results= Parallel(n_jobs=self.n_jobs,prefer="threads") ( delayed (self._optimize_single_column ) (col,df[col]) for col in df.columns )

            df_optimized= pd.DataFrame(dict(results))
            del results
            gc.collect()    

            if stats_before is not None :

                stats_after = df_optimized[numeric_cols].describe()

                if not np.allclose(stats_before.fillna(0),stats_after.fillna(0),rtol=1e-05):
                    
                    logger.warning("Data Integrity Check Mismatch! Reviewing numberic precision")
                    
            final_mem= df.memory_usage(deep=True).sum() /1024**2
            logger.info(f" Optimization Complete : Final Size {final_mem :.2f}MB")
            logger.info(f"Savings : {100* (initial_mem-final_mem)/initial_mem:.2f}%")
            return df_optimized

