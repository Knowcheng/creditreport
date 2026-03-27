# -*- coding: utf-8 -*-
"""
Created on Sun Sep 29 16:08:13 2024

@author: 91600
"""

import logging
from typing import  List, Optional
import pdfplumber
import pandas as pd






class PDFExtractor:
    def __init__(self, path: str):
        self.path = path

    def extract_text(self, page_number: Optional[int] = None) -> str:
        try:
            with pdfplumber.open(self.path) as pdf:
                # 如果 page_number 为 None，则提取所有页面
                if page_number is None:
                    page_number = len(pdf.pages)
                elif page_number > len(pdf.pages):
                    raise ValueError(f"报告页数小于{page_number}页，可能不是征信报告.")
                # 提取指定页数的文本
                return ''.join(page.extract_text() for page in pdf.pages[:page_number])
        except Exception as e:
            logging.error(f"PDF文本提取失败: {e}")
            raise

    def extract_tables(self) -> List[List[List[str]]]:
        try:
            with pdfplumber.open(self.path) as pdf_file:
                tables = []
                for page in pdf_file.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table in page_tables:
                            if table:
                                if tables and len(table[0]) == len(tables[-1][0]):
                                    tables[-1] += table                                    
                                else:                        
                                    tables.append(table)
            return tables
        except Exception as e:
            logging.error(f"PDF表格提取失败: {e}")
            raise
    def clean_data(self,nested_list: List[List[List[str]]]) -> List[List[List[str]]]:
        if not nested_list:
            raise ValueError('你上传的文件不是征信报告')
        for i in range(len(nested_list)):
            for j in range(len(nested_list[i])):
                for k in range(len(nested_list[i][j])):
                    if isinstance(nested_list[i][j][k], str):
                        nested_list[i][j][k] = nested_list[i][j][k].replace('\n', '')
        return nested_list
    def find_table(self, x: str, y: str = None, s: int = 1, e: int = None) -> Optional[pd.DataFrame]:
        if self.path is None or x is None:
            return None
        df = None
        with pdfplumber.open(self.path) as f:
            spage = s - 1 if s > 1 else 0
            epage = e if e is not None else len(f.pages)
            for i in range(spage, epage):
                for tb in f.pages[i].extract_tables():
                    if tb is not None and x in str(tb):
                        if y is not None and y not in str(tb):
                            next_page_tables = f.pages[i + 1].extract_tables() if (i + 1) < len(f.pages) else []
                            if next_page_tables:
                                for a in next_page_tables[0]:
                                    tb.append(a)
                        df = self.create_dataframe(tb)
                        if df is not None:
                            break
                if df is not None:
                    break
        return df

    @staticmethod
    def create_dataframe(tb: List[List[str]]) -> Optional[pd.DataFrame]:
        if tb is None:
            return None

        columns = tb[0]
        data = tb[1:]

        max_len = max(len(row) for row in data)
        if len(columns) < max_len:
            for i in range(len(columns), max_len):
                columns.append(f'col_{i}')

        for row in data:
            while len(row) < len(columns):
                row.append(None)

        return pd.DataFrame(data, columns=columns)
    @staticmethod
    def get_index(data: list, ob_str_1: str,ob_str_2:str=None,start_i: int = 0, end_i: int = None, start_j: int = 0, end_j: int = None):
        index_list = []
        end_i = end_i if end_i is not None else len(data)
        # print(ob_str_1,ob_str_2)
        # print('end_i',end_i)
        for i in range(start_i, min(end_i, len(data))):
            # print('i',i)
            sublist = data[i]
            end_j_local = end_j if end_j is not None else len(sublist)
            
            for j in range(start_j, min(end_j_local, len(sublist))):
                
                subsublist = sublist[j]
                # print(subsublist)
                if (subsublist is not None) and (ob_str_1 in subsublist) and (ob_str_2 is None or ob_str_2 in subsublist):
                    # 找到包含关键字的二级子列表位置
                    index_list.append((i, j))
        
            
        return index_list
    @staticmethod
    def flatten_dict(d, parent_key='', sep='_'):
        if d is None:
            return d
        else:
            
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(PDFExtractor.flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)
    @staticmethod
    def fill_none_with_empty_string(d):
        return {k: (v if v is not None else '') for k, v in d.items()}
    @staticmethod
    def remove_sublist_containing_text(nested_list, text):
        return [
            [sublist for sublist in inner_list if text not in sublist]
            for inner_list in nested_list
        ]