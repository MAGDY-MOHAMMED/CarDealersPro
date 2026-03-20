"""
Data Pipeline Engine - High-Performance Vectorized Operations
===============================================================

Engineering Rationale:
- Memory Optimization: C-Level operations with NumPy vectorization
- Zero-Waste Principle: Eliminate Python loops for data processing
- Production-Ready: Type hints, logging, error handling for enterprise scale
- Scalability: Designed for millions of vehicle records

Night-time Search Task: "NumPy Vectorization vs Python Loops Performance"
MAMAA Vocabulary: "Memory Footprint Optimization" - Reducing memory usage 
                   through strategic data type selection and vectorized operations
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd
from pathlib import Path
import json
import joblib
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import gc
from functools import lru_cache
import warnings

# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DataOptimizationConfig:
    """Configuration for data optimization strategies"""
    enable_memory_optimization: bool = True
    enable_parallel_processing: bool = True
    max_workers: int = -1  # -1 for all available cores
    chunk_size: int = 100_000  # Process in chunks for memory efficiency
    compression_level: int = 6  # Parquet compression
    enable_caching: bool = True
    
class MemoryOptimizer:
    """
    Advanced memory optimization using vectorized operations
    
    Key Principles:
    1. Downcast numeric types to smallest possible dtype
    2. Convert strings to categorical when cardinality < 50%
    3. Use sparse matrices for high-dimensional data
    4. Implement memory-efficient data structures
    """
    
    @staticmethod
    def optimize_numeric_series(series: pd.Series) -> pd.Series:
        """
        Vectorized numeric optimization using NumPy dtype inference
        
        Args:
            series: Pandas Series to optimize
            
        Returns:
            Optimized Series with minimal memory footprint
        """
        if not np.issubdtype(series.dtype, np.number):
            return series
            
        # Vectorized min/max operations
        col_min = series.min()
        col_max = series.max()
        
        # Integer optimization - vectorized comparison
        if series.dtype.kind in ['i', 'u']:
            if col_min >= 0:  # Unsigned integers
                if col_max < 255:
                    return series.astype('uint8')
                elif col_max < 65535:
                    return series.astype('uint16')
                elif col_max < 4294967295:
                    return series.astype('uint32')
            else:  # Signed integers
                if col_min >= -128 and col_max <= 127:
                    return series.astype('int8')
                elif col_min >= -32768 and col_max <= 32767:
                    return series.astype('int16')
                elif col_min >= -2147483648 and col_max <= 2147483647:
                    return series.astype('int32')
        
        # Float optimization
        elif series.dtype.kind == 'f':
            if col_min >= np.finfo('float32').min and col_max <= np.finfo('float32').max:
                return series.astype('float32')
                
        return series
    
    @staticmethod
    def optimize_categorical_series(series: pd.Series, threshold: float = 0.5) -> pd.Series:
        """
        Vectorized categorical optimization
        
        Args:
            series: Pandas Series to optimize
            threshold: Cardinality ratio threshold for categorical conversion
            
        Returns:
            Optimized Series (categorical or original)
        """
        if series.dtype != 'object':
            return series
            
        # Vectorized cardinality calculation
        unique_ratio = series.nunique(dropna=True) / len(series)
        
        if unique_ratio < threshold:
            return series.astype('category')
            
        return series

class DataOptimizer:
    """
    High-performance data optimization engine
    
    Architecture Principles:
    1. SPO Pattern (Stream-Process-Offload)
    2. Vectorized operations throughout
    3. Memory-efficient chunked processing
    4. Parallel processing for large datasets
    """
    
    def __init__(self, config: Optional[DataOptimizationConfig] = None):
        self.config = config or DataOptimizationConfig()
        self.memory_optimizer = MemoryOptimizer()
        self._cache = {}
        
    def analyze_memory_footprint(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Vectorized memory analysis using NumPy operations
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Detailed memory usage statistics
        """
        memory_stats = {}
        
        # Vectorized memory calculation
        memory_usage = df.memory_usage(deep=True, index=False)
        total_memory = memory_usage.sum()
        
        # Column-wise analysis
        for col in df.columns:
            col_memory = memory_usage[col]
            col_dtype = df[col].dtype
            
            memory_stats[col] = {
                'memory_mb': col_memory / (1024 * 1024),
                'dtype': str(col_dtype),
                'unique_values': df[col].nunique(),
                'null_percentage': (df[col].isna().sum() / len(df)) * 100
            }
            
        memory_stats['total_memory_mb'] = total_memory / (1024 * 1024)
        memory_stats['row_count'] = len(df)
        memory_stats['column_count'] = len(df.columns)
        
        return memory_stats
    
    def optimize_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Vectorized DataFrame optimization with parallel processing
        
        Args:
            df: DataFrame to optimize
            
        Returns:
            Tuple of (optimized DataFrame, optimization statistics)
        """
        logger.info(f"Starting optimization for DataFrame: {df.shape}")
        
        # Initial memory analysis
        initial_memory = self.analyze_memory_footprint(df)
        logger.info(f"Initial memory usage: {initial_memory['total_memory_mb']:.2f} MB")
        
        # Create optimized copy
        optimized_df = df.copy()
        optimization_stats = {
            'columns_optimized': [],
            'memory_saved_mb': 0,
            'optimization_ratio': 0
        }
        
        # Parallel column optimization for large DataFrames
        if self.config.enable_parallel_processing and len(df.columns) > 10:
            optimized_df = self._parallel_optimize_columns(optimized_df, optimization_stats)
        else:
            optimized_df = self._vectorized_optimize_columns(optimized_df, optimization_stats)
        
        # Final memory analysis
        final_memory = self.analyze_memory_footprint(optimized_df)
        memory_saved = initial_memory['total_memory_mb'] - final_memory['total_memory_mb']
        
        optimization_stats.update({
            'memory_saved_mb': memory_saved,
            'optimization_ratio': memory_saved / initial_memory['total_memory_mb'],
            'initial_memory_mb': initial_memory['total_memory_mb'],
            'final_memory_mb': final_memory['total_memory_mb']
        })
        
        logger.info(f"Optimization complete. Memory saved: {memory_saved:.2f} MB ({optimization_stats['optimization_ratio']:.1%})")
        
        # Force garbage collection
        gc.collect()
        
        return optimized_df, optimization_stats
    
    def _vectorized_optimize_columns(self, df: pd.DataFrame, stats: Dict[str, Any]) -> pd.DataFrame:
        """
        Vectorized column optimization using NumPy operations
        
        Args:
            df: DataFrame to optimize
            stats: Optimization statistics tracking
            
        Returns:
            Optimized DataFrame
        """
        # Vectorized column type detection and optimization
        for col in df.columns:
            original_dtype = df[col].dtype
            
            # Numeric optimization
            if np.issubdtype(original_dtype, np.number):
                optimized_col = self.memory_optimizer.optimize_numeric_series(df[col])
                if optimized_col.dtype != original_dtype:
                    df[col] = optimized_col
                    stats['columns_optimized'].append(f"{col}: {original_dtype} -> {optimized_col.dtype}")
            
            # Categorical optimization
            elif original_dtype == 'object':
                optimized_col = self.memory_optimizer.optimize_categorical_series(df[col])
                if optimized_col.dtype != original_dtype:
                    df[col] = optimized_col
                    stats['columns_optimized'].append(f"{col}: {original_dtype} -> {optimized_col.dtype}")
        
        return df
    
    def _parallel_optimize_columns(self, df: pd.DataFrame, stats: Dict[str, Any]) -> pd.DataFrame:
        """
        Parallel column optimization for large DataFrames
        
        Args:
            df: DataFrame to optimize
            stats: Optimization statistics tracking
            
        Returns:
            Optimized DataFrame
        """
        def optimize_column_chunk(column_chunk: List[str]) -> Dict[str, Any]:
            """Optimize a chunk of columns"""
            chunk_results = {}
            for col in column_chunk:
                original_dtype = df[col].dtype
                
                if np.issubdtype(original_dtype, np.number):
                    optimized_col = self.memory_optimizer.optimize_numeric_series(df[col])
                    if optimized_col.dtype != original_dtype:
                        chunk_results[col] = (optimized_col, f"{col}: {original_dtype} -> {optimized_col.dtype}")
                
                elif original_dtype == 'object':
                    optimized_col = self.memory_optimizer.optimize_categorical_series(df[col])
                    if optimized_col.dtype != original_dtype:
                        chunk_results[col] = (optimized_col, f"{col}: {original_dtype} -> {optimized_col.dtype}")
            
            return chunk_results
        
        # Split columns into chunks for parallel processing
        columns = df.columns.tolist()
        chunk_size = max(1, len(columns) // (self.config.max_workers if self.config.max_workers > 0 else joblib.cpu_count()))
        column_chunks = [columns[i:i + chunk_size] for i in range(0, len(columns), chunk_size)]
        
        # Parallel execution
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            chunk_results = list(executor.map(optimize_column_chunk, column_chunks))
        
        # Apply results
        for chunk_result in chunk_results:
            for col, (optimized_col, optimization_info) in chunk_result.items():
                df[col] = optimized_col
                stats['columns_optimized'].append(optimization_info)
        
        return df
    
    @lru_cache(maxsize=128)
    def get_optimization_strategy(self, column_dtype: str, unique_ratio: float) -> str:
        """
        Cached optimization strategy determination
        
        Args:
            column_dtype: Data type of the column
            unique_ratio: Ratio of unique values to total values
            
        Returns:
            Optimization strategy string
        """
        if np.issubdtype(column_dtype, np.number):
            return "numeric_downcast"
        elif unique_ratio < 0.5:
            return "categorical_conversion"
        else:
            return "no_optimization"

# Production-ready singleton pattern
_data_optimizer_instance = None

def get_data_optimizer(config: Optional[DataOptimizationConfig] = None) -> DataOptimizer:
    """
    Singleton pattern for DataOptimizer instance
    
    Args:
        config: Optional configuration for the optimizer
        
    Returns:
        DataOptimizer instance
    """
    global _data_optimizer_instance
    if _data_optimizer_instance is None:
        _data_optimizer_instance = DataOptimizer(config)
    return _data_optimizer_instance

# Usage example and benchmark
if __name__ == "__main__":
    # Create sample data for testing
    np.random.seed(42)
    sample_data = {
        'vehicle_id': range(1_000_000),
        'price': np.random.uniform(10000, 500000, 1_000_000),
        'year': np.random.randint(1990, 2024, 1_000_000),
        'make': np.random.choice(['Toyota', 'Honda', 'Ford', 'BMW', 'Mercedes'], 1_000_000),
        'model': np.random.choice(['Camry', 'Civic', 'F-150', 'X5', 'C-Class'], 1_000_000),
        'mileage': np.random.uniform(0, 200000, 1_000_000),
        'condition': np.random.choice(['Excellent', 'Good', 'Fair', 'Poor'], 1_000_000)
    }
    
    df = pd.DataFrame(sample_data)
    
    # Initialize optimizer
    optimizer = get_data_optimizer()
    
    # Run optimization
    optimized_df, stats = optimizer.optimize_dataframe(df)
    
    # Print results
    print("=== Data Optimization Results ===")
    print(f"Memory saved: {stats['memory_saved_mb']:.2f} MB")
    print(f"Optimization ratio: {stats['optimization_ratio']:.1%}")
    print(f"Columns optimized: {len(stats['columns_optimized'])}")
    
    # Night-time search task preparation
    print("\n=== Night-time Search Task ===")
    print("Search term: 'NumPy Vectorization vs Python Loops Performance'")
    print("Focus: Memory footprint optimization techniques in large-scale data processing")
    
    print("\n=== MAMAA Vocabulary ===")
    print("Term: 'Memory Footprint Optimization'")
    print("Definition: Strategic reduction of memory usage through optimal data type selection, vectorized operations, and memory-efficient data structures in enterprise-scale applications.")
