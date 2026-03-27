# -*- coding: utf-8 -*-
"""
Created on Wed Oct  9 19:46:30 2024

@author: chengkang
"""

import logging
import streamlit as st
from io import BytesIO
import socket
from tqdm import tqdm
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import re
import pdfplumber
import pandas as pd
from PyPDF2 import PdfReader
import time

import output20230628 as ot  # 假设这是一个自定义模块
# import PDFExtractor as cp
# from credit_pdfextract import PDFExtractor as cp
import PDFExtractor as cp
# from output_excel import output_excel as ot
# import output20230628 as ot
from datetime import datetime,timedelta
# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class ReportInfo:
    report_number: str
    company_name: str
    credit_num:str
    credit_code: str
    query_org: str
    report_date: str



class DataCleaner:
    @staticmethod
    def clean_data(nested_list: List[List[List[str]]]) -> List[List[List[str]]]:
        if not nested_list:
            raise ValueError('你上传的文件不是征信报告')
        
        for i in range(len(nested_list)):
            for j in range(len(nested_list[i])):
                for k in range(len(nested_list[i][j])):
                    if isinstance(nested_list[i][j][k], str):
                        nested_list[i][j][k] = nested_list[i][j][k].replace('\n', '')
        return nested_list
#企业征信自查版解析程序
class CR_CIParser:
    def __init__(self, path: str, text: str, tables: List[List[List[str]]]): 
        self.text = text
        self.tables = tables
        self.path = path
    def extract_report_info(self) -> ReportInfo:
        patterns = {
            "report_number": r"NO.(\d+)",
            "company_name": r"企业名称：(.+?)\s",
            "credit_num": r"中征码：(.+?)\s",
            "credit_code": r"统一社会信用代码[:：]\s*([0-9A-Z]{18})",
            "query_org": r"查询机构：(.+?)\s",
            "report_date": r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
            # "注册资本":r"注册资本折人民币合计(.*?)万元"
        }
        
        info = {}
        # print(self.text)
        for key, pattern in patterns.items():
            match = re.search(pattern, self.text)
            if match:
                info[key] = match.group(1).strip()
                # print(info[key])
            else:
                info[key]=None
                logging.warning(f"未找到{key}信息")
        
        return ReportInfo(**info)

   
    
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
                    items.extend(CR_CIParser.flatten_dict(v, new_key, sep=sep).items())
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
    def get_com_base_data(self, report_info):
        try:
            res_capital = re.search(r"注册资本折人民币合计(.*?)万元", self.text).group(1).strip()
        except Exception:
            res_capital = ''
        if self.tables:
            com_id_dict = {item[0]: item[1] for item in self.tables[0]}
            
            com_base = self.find_table('经济类型', '存续状态')
            if not com_base.empty and com_base is not None:
                com_base = com_base.iloc[:, :2]
                com_base = com_base.T.reset_index()
                new_column = com_base.iloc[0, :]
                com_base = com_base.iloc[1:]
                com_base.rename(columns=new_column, inplace=True)
                com_dict = {col: ','.join(map(str, com_base[col].tolist())) for col in com_base.columns}
            else:
                raise ValueError('你上传的报告没有基本信息，请检查')
            com_dict = {**com_dict, **com_id_dict}
            com_dict['报告编号'] = report_info.report_number
            com_dict['报告日期'] = report_info.report_date
            com_dict['注册资本'] = res_capital
            com_dict['解析时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            com_dict = None
        return com_dict

    def get_com_person_data(self, report_info):
        holder_df = self.find_table('出资方', '信息来源机构')
        manage_df = self.find_table('职位', '信息来源机构')

        holder_dict = None
        if holder_df is not None:
            holder_df = holder_df.iloc[:-1, :]
            holder_dict = holder_df.to_dict(orient='list')
            holder_dict['报告编号'] = [report_info.report_number]
            holder_dict['统一社会信用代码'] = [report_info.credit_code]

        manage_dict = None
        if manage_df is not None:
            manage_df = manage_df.iloc[:-1, :]
            manage_dict = manage_df.to_dict(orient='list')
            manage_dict['报告编号'] = [report_info.report_number]
            manage_dict['统一社会信用代码'] = [report_info.credit_code]

        return holder_dict, manage_dict

    #信息概要
    def get_summary_data(self,report_info):
        if self.tables:
            
            summary_dict_1 = dict(zip(self.tables[1][0],self.tables[1][1]))
            summary_dict_1['报告编号'] = report_info.report_number
            summary_dict_1['统一社会信用代码'] = report_info.credit_code
            
        else:
            summary_dict_1=None
        
        return summary_dict_1

    def get_summary_data_2(self,report_info):
        if self.tables:
            summary_dict_2 = {"借贷交易":                      
                               {"正常类余额":float(self.tables[1][3][1])-float(self.tables[1][4][1])-float(self.tables[1][5][1])-float(self.tables[1][6][1]),
                                "被追偿类余额":float(self.tables[1][4][1]),
                                "关注类余额":float(self.tables[1][5][1]),
                                "不良类余额":float(self.tables[1][6][1])},
                             "担保交易":                        
                                   {"正常类余额":float(self.tables[1][3][3])-float(self.tables[1][4][3])-float(self.tables[1][5][3]),                            
                                    "关注类余额":float(self.tables[1][4][3]),
                                    "不良类余额":float(self.tables[1][5][3])}                           
                                }
            summary_dict_2['报告编号'] = report_info.report_number
            summary_dict_2['统一社会信用代码'] = report_info.credit_code
        else:
            summary_dict_2= None
        
        return summary_dict_2
    def get_neg_summary_data(self,report_info):
    #负面信息    
        if self.tables:
            neg_info_dict =  dict(zip(self.tables[2][0],self.tables[2][1]))
            neg_info_dict['报告编号'] = report_info.report_number
            neg_info_dict['统一社会信用代码'] = report_info.credit_code
        else:
            neg_info_dict = None
        
        return neg_info_dict

    #未结清信贷及授信信息概要
    def get_outstanding_bad_summary_data(self,report_info):
        no_repay_bad_summary_dict = None  # Initialize the variable at the beginning
        
        if self.tables:
            no_pay_summary_index = CR_CIParser.get_index(self.tables, '由资产管理公司处置的债务')
            if len(no_pay_summary_index) != 0 and len(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1]]) == 9:
                no_repay_bad_summary_dict = {
                    "由资产管理公司处置的债务": {
                        "账户数": self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][0],
                        "余额": float(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][1]),
                        "最近一次处置日期": self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][2]
                    },
                    "垫款": {
                        "账户数": self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][3],
                        "余额": float(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][4]),
                        "最近一次还款日期": self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][5]
                    },
                    "逾期": {
                        "本金": float(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][6]),
                        "利息及其他": float(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][7]),
                        "总额": float(self.tables[no_pay_summary_index[0][0]][no_pay_summary_index[0][1] + 2][8])
                    }
                }
                no_repay_bad_summary_dict['报告编号'] = report_info.report_number
                no_repay_bad_summary_dict['统一社会信用代码'] = report_info.credit_code
        else:
            no_repay_bad_summary_dict = None  # Explicitly assign None to the variable
       
        return no_repay_bad_summary_dict


         
    #提取未结清信贷及授信信息概要
    # 1.找出出现“正常类”关键字所在列表位置
    # 2.然后把这些列表转换成字典
    def get_loan_account(self, loan_type: str, zc_index: Tuple[int, int]) -> Optional[Dict[str, str]]:
        if not self.tables:
            return None 
        try:
            loan_index = self.get_index(self.tables, loan_type, None, zc_index[0], zc_index[0] + 1)
            if not loan_index:
                return None

            row, col = loan_index[0]
            return {
                "账户数": self.tables[row][col][1],
                "余额": self.tables[row][col][2],
                "关注类账户数": self.tables[row][col][3],
                "关注类余额": self.tables[row][col][4],
                "不良类账户数": self.tables[row][col][5],
                "不良类余额": self.tables[row][col][6]
            }
        except IndexError:
            logging.warning(f"索引错误: 处理 {loan_type} 时发生错误")
            return None
        except Exception as e:
            logging.error(f"处理 {loan_type} 时发生错误: {e}")
            return None

    def get_outstanding_account_data(self, report_info: ReportInfo) -> Optional[Dict]:
       if not self.tables:
           return None

       try:
           zc_index = self.get_index(self.tables, '正常类')
           if not zc_index:
               return None

           loan_types = ['中长期借款', '短期借款', '循环透支', '贴现', '银行承兑汇票', '信用证', '银行保函', '其他担保交易']
           summary_dict = {}

           for loan_type in loan_types:
               loan_account = self.get_loan_account(loan_type, zc_index[0])
               if loan_account:
                   summary_dict[loan_type] = loan_account

           if summary_dict:
               summary_dict['报告编号'] = report_info.report_number
               summary_dict['统一社会信用代码'] = report_info.credit_code
               return summary_dict
           
           return None

       except Exception as e:
           logging.error(f"Error in get_outstanding_account_data: {e}")
           return None
    def get_circle_summary_data(self,report_info):
        if not self.tables:
            return None   
        circle_credit_index = self.get_index(self.tables,'非循环信用额度')   
        if len(circle_credit_index)>0:
            no_circle_credit_total = self.tables[circle_credit_index[0][0]][2][0]
            no_circle_credit_used = self.tables[circle_credit_index[0][0]][2][1]
            no_circle_credit_rest = self.tables[circle_credit_index[0][0]][2][2]
            circle_credit_total = self.tables[circle_credit_index[0][0]][2][3]
            circle_credit_used = self.tables[circle_credit_index[0][0]][2][4]
            circle_credit_rest = self.tables[circle_credit_index[0][0]][2][5]
            
            credit_summary_dict = {"非循环信用额度":
                                                {"总额":no_circle_credit_total,
                                                "已用额度":no_circle_credit_used,
                                                "剩余可用额度":no_circle_credit_rest},
                                 "循环信用额度":
                                              {"总额":circle_credit_total,
                                              "已用额度":circle_credit_used,
                                              "剩余可用额度":circle_credit_rest}                                 
                                     }
            credit_summary_dict['报告编号'] = report_info.report_number
            credit_summary_dict['统一社会信用代码'] = report_info.credit_code
        else:
            credit_summary_dict=None
        # print("Starting circle_summary") 
        return credit_summary_dict
    #相关还款责任信息概要，想不搞担保交易。
    def get_repay_liability_summary_data(self,report_info):
        
        repay_liability_summary_df = self.find_table('被追偿业务','合计') 
       
        if repay_liability_summary_df is not None :
        
            if repay_liability_summary_df.columns[4]=='col_4':
                
                columns_to_use = [repay_liability_summary_df.columns[1], repay_liability_summary_df.columns[2]]
            else:
                columns_to_use = [repay_liability_summary_df.columns[1], repay_liability_summary_df.columns[4]]
        
            # 初始化字典结构
            repay_liability_summary_dict = {col: {} for col in columns_to_use}
            
            # 动态处理每一行
            for i in range(1, len(repay_liability_summary_df)-1):
                key = repay_liability_summary_df.iloc[i, 0]
                if key:
                    # 更新第一个字段
                    repay_liability_summary_dict[columns_to_use[0]][key] = {
                        repay_liability_summary_df.iloc[0, 1]: repay_liability_summary_df.iloc[i, 1],
                        repay_liability_summary_df.iloc[0, 2]: repay_liability_summary_df.iloc[i, 2],
                        repay_liability_summary_df.iloc[0, 3]: repay_liability_summary_df.iloc[i, 3]
                    }
                    # 更新第二个字段
                    repay_liability_summary_dict[columns_to_use[1]][key] = {
                       repay_liability_summary_df.iloc[0, 1]: repay_liability_summary_df.iloc[i, 4],
                        repay_liability_summary_df.iloc[0, 2]: repay_liability_summary_df.iloc[i, 5],
                        repay_liability_summary_df.iloc[0, 3]: repay_liability_summary_df.iloc[i, 6],
                        repay_liability_summary_df.iloc[0, 7]: repay_liability_summary_df.iloc[i, 7],
                        repay_liability_summary_df.iloc[0, 8]: repay_liability_summary_df.iloc[i, 8]
                    }
            repay_liability_summary_dict['报告编号'] = report_info.report_number
            repay_liability_summary_dict['统一社会信用代码'] =report_info.credit_code
        else:
            repay_liability_summary_dict=None
        return repay_liability_summary_dict

    #已结清信贷及授信信息概要
    #已结清坏的的信息概要
    def extract_repayed_bad_summary(self, index):
        if not self.tables:
            return None 
        try:
            # if len(tables[index[0][0]][index[0][1]]) == 6:
            return {
                "由资产管理公司处置的债务": {
                    "账户数": self.tables[index[0][0]][index[0][1]+2][0],
                    "金额": float(self.tables[index[0][0]][index[0][1]+2][1]),
                    "处置完成日期": self.tables[index[0][0]][index[0][1]+2][2]
                },
                "垫款": {
                    "账户数": self.tables[index[0][0]][index[0][1]+2][3],
                    "金额": float(self.tables[index[0][0]][index[0][1]+2][4]),
                    "结清日期": self.tables[index[0][0]][index[0][1]+2][5]
                }
            }
        except Exception as e:
            print(f"Error extracting repay data: {e}")
            # return None
    def get_payed_bad_summary_data(self,report_info):
        if not self.tables:
            return None 
        try:
            no_pay_summary_index = self.get_index(self.tables, '由资产管理公司处置的债务')
            valid_indices = [idx for idx in no_pay_summary_index if len(self.tables[idx[0]][idx[1]]) == 6]
            if valid_indices :
                repayed_bad_summary_dict = self.extract_repayed_bad_summary(self.tables, valid_indices)
                if repayed_bad_summary_dict:
                    repayed_bad_summary_dict['报告编号'] = report_info.report_number
                    repayed_bad_summary_dict['统一社会信用代码'] = report_info.credit_code
                    return repayed_bad_summary_dict
            return None
        except Exception as e:
            print(f"Error in get_payed_bad_summary_data: {e}")
            return None
    #已结清授信信息概要
    def get_payed_summary_data(self,report_info):
        if not self.tables:
            return None 
        def extract_loan_data(loan_type, start_row, end_row):
            try:
                loan_index = self.get_index(data=self.tables,ob_str_1=loan_type,  start_i=start_row, end_i=end_row)
                if loan_index:
                    row, col = loan_index[0]
                    return {
                        "正常类账户数": self.tables[row][col][1],
                        "关注类账户数": self.tables[row][col][2],
                        "不良类账户数": self.tables[row][col][3],
                    }
                else:
                    return {
                        "正常类账户数": None,
                        "关注类账户数": None,
                        "不良类账户数": None,
                    }
            except Exception as e:
                # Log or handle the exception if needed
                print(f"Error extracting data for {loan_type}: {e}")
                return {
                    "正常类账户数": None,
                    "关注类账户数": None,
                    "不良类账户数": None,
                }
        
        repay_summary_dict = {}

        try:
            zc_pay_index = self.get_index(data=self.tables,ob_str_1='正常类账户数')
            # print(zc_pay_index)
            if zc_pay_index:
                start_row, end_row = zc_pay_index[0][0], zc_pay_index[0][0] + 1
                
                repay_summary_dict = {
                    "中长期借款": extract_loan_data('中长期借款', start_row, end_row),
                    "短期借款": extract_loan_data('短期借款', start_row, end_row),
                    "循环透支": extract_loan_data('循环透支', start_row, end_row),
                    "贴现": extract_loan_data('贴现', start_row, end_row),
                    "银行承兑汇票": extract_loan_data('银行承兑汇票', start_row, end_row),
                    "信用证": extract_loan_data('信用证', start_row, end_row),
                    "银行保函": extract_loan_data('银行保函', start_row, end_row),
                    "其他担保交易": extract_loan_data('其他担保交易', start_row, end_row),
                }
                
                repay_summary_dict['报告编号'] = report_info.report_number
                repay_summary_dict['统一社会信用代码'] = report_info.credit_code
            else:
                repay_summary_dict = None

        except Exception as e:
            # Log or handle the exception if needed
            print(f"Error processing repayment summary data: {e}")
            repay_summary_dict = None
        
        return repay_summary_dict

    #信贷记录明细
    #1.被追偿业务
    def get_recovered_detail_data(self,report_info):
       
        if not self.tables:
            return None 
        tables = self.tables
        recovered_detail_index = self.get_index(tables,'债权机构','业务种类')
        # print('recovered_detail_index',recovered_detail_index)
        if  len(recovered_detail_index)>0:
            recovered_detail_dict = {"账户编号":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][0],
                                     "债权机构":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][1],
                                     "业务种类":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][2],
                                     "接收日期":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][3],
                                     "币种":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][4],
                                     "借款金额":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][5],
                                     "余额":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][6],
                                     "关闭日期":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][7],
                                     "信息报告日期":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+2][8],
                                     "五级分类":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][1],
                                     "最近一次还款日期":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][2],
                                     "最近一次还款总额":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][3],
                                     "最近一次还款形式":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][4],
                                     "历史表现":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][5],
                                     "初始债权人名称":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][6],
                                     "原债权种类":self.tables[recovered_detail_index[0][0]][recovered_detail_index[0][1]+3][7]
                                     }
            recovered_detail_dict['报告编号'] = report_info.report_number
            recovered_detail_dict['统一社会信用代码'] =report_info.credit_code
        else:
            recovered_detail_dict=None
        return recovered_detail_dict
    #2.未结清借款
    # （1）中长期和短期借款的字段是一样的，但循环透支不一样。
    # （2）如果都没有，直接用index判断，输出None.如果只有中长期或短期，字段就合并。通过“剩余还款”是否在列表中进行判断。
    # （3）中长期或短期或循环透支，都可能存在多条记录。通过两个索引之间差值是否是3的倍数来判断。直接在原来的取数逻辑上+3。
    def get_nopay_loan_detail_data(self, report_info: dict) -> tuple:
        if not self.tables:
            return None 
        tables = self.tables
        nopay_loan_detail_index = self.get_index(tables, '担保方式', '余额')
       
        # print(nopay_loan_detail_index)
        data_loan_dicts, data_circle_dicts = [], []

        if not nopay_loan_detail_index:
            return data_loan_dicts, data_circle_dicts

        def process_data(headers, data_rows, report_info):
            flattened_headers = [item for sublist in headers for item in sublist]
            result = []
            for i in range(0, len(data_rows) // 3):
                start_index = i * 3
                if start_index <= len(data_rows):
                    data_set = data_rows[start_index:start_index + 3]
                    combined_data = [item for sublist in data_set for item in sublist]
                    detail_dict = dict(zip(flattened_headers, combined_data))
                    detail_dict.update({
                        '报告编号': report_info.report_number,
                        '统一社会信用代码': report_info.credit_code
                    })
                    result.append(detail_dict)
            # print(result)
            return result

        table = self.tables[nopay_loan_detail_index[0][0]]
        has_bi = '笔' in str(table)

        if has_bi:
            bi_index = self.get_index(table, '笔')
          
        if len(nopay_loan_detail_index) == 1:
            if has_bi:
                headers = table[1:4]
                if len(bi_index) > 1:
                    data_rows = table[4:bi_index[1][0]] + table[bi_index[1][0]+3:]
                else:
                    data_rows = table[4:]
            else:
                headers = table[:3]
                data_rows = table[3:]
            data_loan_dicts = process_data(headers, data_rows, report_info)

        elif len(nopay_loan_detail_index) == 2:
            if '剩余还款月数' not in str(table):
                if has_bi:
                    headers = table[1:4]
                    if  nopay_loan_detail_index[1][0]!= nopay_loan_detail_index[0][0]:
                        table_1 =  self.tables[nopay_loan_detail_index[1][0]]
                        data_rows = table[4:] + table_1[4:]
                    else:
                        data_rows = table[4:bi_index[1][0]] + table[bi_index[1][0]+4:]
                    
                else:
                    headers = table[:3]
                    data_rows = table[nopay_loan_detail_index[0][1]+2:nopay_loan_detail_index[1][1]-1] + table[nopay_loan_detail_index[1][1]+2:]
                    
                data_loan_dicts = process_data(headers, data_rows, report_info)
            else:
                if has_bi:
                    headers_loan = table[1:4]
                    data_rows_loan = table[nopay_loan_detail_index[0][1]+2:nopay_loan_detail_index[1][1]-2]
                    headers_circle = table[nopay_loan_detail_index[1][1]-1:nopay_loan_detail_index[1][1]+2]
                    data_rows_circle = table[nopay_loan_detail_index[1][1]+2:]
                else:
                    headers_loan = table[:3]
                    data_rows_loan = table[nopay_loan_detail_index[0][1]+2:nopay_loan_detail_index[1][1]-1]
                    headers_circle = table[nopay_loan_detail_index[1][1]-1:nopay_loan_detail_index[1][1]+2]
                    data_rows_circle = table[nopay_loan_detail_index[1][1]+2:]

                data_loan_dicts = process_data(headers_loan, data_rows_loan, report_info)
                data_circle_dicts = process_data(headers_circle, data_rows_circle, report_info)

        elif len(nopay_loan_detail_index) == 3:
            
            if has_bi:
                headers_loan = table[1:4]
                data_rows_loan = table[4:bi_index[1][0]] + table[bi_index[1][0]+4:]
                if  nopay_loan_detail_index[2][0]!= nopay_loan_detail_index[1][0]:
                    table = self.tables[nopay_loan_detail_index[2][0]]
                    headers_circle = table[1:4]
                    data_rows_circle = table[4:]
                else:
                    
                    headers_circle = table[bi_index[2][0]:bi_index[1][0]+3]
                    data_rows_circle = table[bi_index[1][0]+3:]
            else:
                headers_loan = table[:3]
                data_rows_loan = table[nopay_loan_detail_index[0][1]+2:nopay_loan_detail_index[1][1]-1] + table[nopay_loan_detail_index[1][1]+2:nopay_loan_detail_index[2][1]-1]
                if  nopay_loan_detail_index[2][0]!= nopay_loan_detail_index[1][0]:
                    table = self.tables[nopay_loan_detail_index[2][0]]
                    headers_circle = table[:3]
                    data_rows_circle = table[3:]
                else:
                    
                    headers_circle = table[nopay_loan_detail_index[2][1]-1:nopay_loan_detail_index[2][1]+2]
                    data_rows_circle = table[nopay_loan_detail_index[2][1]+2:]

            data_loan_dicts = process_data(headers_loan, data_rows_loan, report_info)
            data_circle_dicts = process_data(headers_circle, data_rows_circle, report_info)

        return data_loan_dicts, data_circle_dicts

    #贴现、银行承兑和信用证、银行保函

    def get_nopay_discount_detail_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        nopay_discount_detail_index = self.get_index(tables,'授信机构','逾期本金')
        if len(nopay_discount_detail_index)>0:
            nopay_discount_keys = self.tables[nopay_discount_detail_index[0][0]][nopay_discount_detail_index[0][1]]
            if '授信协议编号' in str(self.tables[nopay_discount_detail_index[0][0]]):
                credit_detail_index = self.get_index('授信额度类型','额度循环标志')
                nopay_discount_data = self.tables[nopay_discount_detail_index[0][0]][nopay_discount_detail_index[0][1]:credit_detail_index[0][1]-1]
            else:
                nopay_discount_data = self.tables[nopay_discount_detail_index[0][0]][nopay_discount_detail_index[0][1]:]
            # Convert the rest of the lists into dictionaries
            nopay_discount_detail_dict = [dict(zip(nopay_discount_keys, values)) for values in nopay_discount_data[1:]]
            nopay_discount_detail_dict=[{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in nopay_discount_detail_dict]
          
        else:
            nopay_discount_detail_dict=None
        return nopay_discount_detail_dict


        #银行承兑和信用证
    def get_bank_letter_detail_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        bank_letter_list = []
        nopay_bankdraf_letter_detail_index = self.get_index(tables,'授信机构','余额')
        nopay_bankdraf_detail_dict=None
        for a in range(len(nopay_bankdraf_letter_detail_index)):
           
            if len(self.tables[nopay_bankdraf_letter_detail_index[a][0]][0])==5:
                bank_letter_list.append(a)
                if len(bank_letter_list)==1:
                    if '笔' in str(self.tables[nopay_bankdraf_letter_detail_index[0][0]]):
                        nopay_bankdraf_keys = self.tables[nopay_bankdraf_letter_detail_index[a][0]][1]
                        nopay_bankdraf_data = self.tables[nopay_bankdraf_letter_detail_index[a][0]][2:]
                    else:
                        nopay_bankdraf_keys = self.tables[nopay_bankdraf_letter_detail_index[a][0]][0]
                        nopay_bankdraf_data = self.tables[nopay_bankdraf_letter_detail_index[a][0]][1:]
                    nopay_bankdraf_detail_dict = [dict(zip(nopay_bankdraf_keys, values)) for values in nopay_bankdraf_data]
                    nopay_bankdraf_detail_dict=[{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in nopay_bankdraf_detail_dict]
                 
                elif len(bank_letter_list)==2:
                    if '笔' in str(self.tables[nopay_bankdraf_letter_detail_index[0][0]]):
                        nopay_bankdraf_keys = self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[0]][0]][1]
                        nopay_bankdraf_data = self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[0]][0]][2:nopay_bankdraf_letter_detail_index[bank_letter_list[1]][1]-1]+ self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[1]][0]][nopay_bankdraf_letter_detail_index[bank_letter_list[1]][1]+1:]
                    else:
                        
                        nopay_bankdraf_keys = self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[0]][0]][0]
                        
                        nopay_bankdraf_data = self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[0]][0]][1:nopay_bankdraf_letter_detail_index[bank_letter_list[1]][1]]+ self.tables[nopay_bankdraf_letter_detail_index[bank_letter_list[1]][0]][nopay_bankdraf_letter_detail_index[bank_letter_list[1]][1]+1:]
                   
                    nopay_bankdraf_detail_dict = [dict(zip(nopay_bankdraf_keys, values)) for values in nopay_bankdraf_data]
                    nopay_bankdraf_detail_dict=[{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in nopay_bankdraf_detail_dict]
             
                else:
                    nopay_bankdraf_detail_dict=None
        return nopay_bankdraf_detail_dict
    #授信信息（需要修复,已修复）
    def get_credit_detail_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        credit_detail_index = self.get_index(tables,'授信额度类型','额度循环标志')
        credit_data_dicts = []
        if len(credit_detail_index)>0:
            if '笔' in str(self.tables[credit_detail_index[0][0]]):
                if '余额变化日期' in str(self.tables[credit_detail_index[0][0]]):
                    
                    replenish_credit_detail_index = self.get_index(tables,'余额','余额变化日期')
                    credit_detail_header = self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:credit_detail_index[0][1]+2]
                    credit_detail_data_rows=self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:replenish_credit_detail_index[0][1]]
                else:
                    credit_detail_header = self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:credit_detail_index[0][1]+2]
                    credit_detail_data_rows=self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]+2:]
                
            else:
                if '余额变化日期' in str(self.tables[credit_detail_index[0][0]]):
                    credit_detail_header = self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:credit_detail_index[0][1]+2]
                    credit_detail_data_rows=self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:replenish_credit_detail_index[0][1]]
                else:
                    credit_detail_header = self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]:credit_detail_index[0][1]+2]
                    credit_detail_data_rows=self.tables[credit_detail_index[0][0]][credit_detail_index[0][1]+2:]
                
            flattened_credit_detail_header = [item for sublist in credit_detail_header for item in sublist]
            for i in range(0,len(credit_detail_data_rows)//2):
                # print('i',i)
                credit_detail_start_index = i * 2
                if credit_detail_start_index<=len(credit_detail_data_rows):
                    credit_detail_data_set = credit_detail_data_rows[credit_detail_start_index:credit_detail_start_index + 2]
                    # print('credit_detail_data_set',credit_detail_data_set)
                    credit_detail_combined_data = [item for sublist in credit_detail_data_set  for item in sublist]
                    credit_detail_dict = dict(zip(flattened_credit_detail_header, credit_detail_combined_data))
                    credit_detail_dict['报告编号'] = report_info.report_number
                    credit_detail_dict['统一社会信用代码'] =report_info.credit_code
                    credit_data_dicts.append(credit_detail_dict)
        return credit_data_dicts
    #已结清信贷明细(需要修复，循环透支和借款不一样,已修复)
    def get_payed_detail_data(self,report_info):
        if not self.tables:
            return None
        payed_data_dicts = []
        tables = self.tables
        payed_detail_index = self.get_index(tables,'最后一次还款日期','历史表现')
        if len(payed_detail_index) > 0:
            if payed_detail_index[0][1] ==0:
               flattened_payed_header = self.tables[payed_detail_index[0][0]-1][-1]+ self.tables[payed_detail_index[0][0]][0]
            else:
                payed_header = self.tables[payed_detail_index[0][0]][payed_detail_index[0][1]-1:payed_detail_index[0][1]+1]
                flattened_payed_header = [item for sublist in payed_header for item in sublist]
            remove_tables = self.remove_sublist_containing_text(tables, '授信机构')
            remove_tables = self.remove_sublist_containing_text(remove_tables, '关闭日期')
            # remove_tables = remove_sublist_containing_text(remove_tables, '笔')
            remove_tables = [[sublist for sublist in inner_list if not any('笔' in (item or '') for item in sublist)] for inner_list in remove_tables]
            payed_data_rows=remove_tables[payed_detail_index[0][0]]
            for i in range(0,len(payed_data_rows)//2):
                payed_start_index = i * 2
                # print( payed_start_loan_index)
                if  payed_start_index<=len(payed_data_rows):
                    payed_data_set = payed_data_rows[payed_start_index: payed_start_index + 2]
                    # print(data_loan_set)
                    payed_combined_data = [item for sublist in payed_data_set for item in sublist]
                    payed_detail_dict = dict(zip(flattened_payed_header, payed_combined_data))
                    payed_detail_dict['报告编号'] = report_info.report_number
                    payed_detail_dict['统一社会信用代码'] =report_info.credit_code
                    payed_data_dicts.append(payed_detail_dict)
                
        else:
            payed_data_dicts = None 
        return payed_data_dicts
    #贴现
    def get_payed_discount_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        payed_discount_index=self.get_index(tables,'授信机构','贴现金额')
        payed_bankdraf_index = self.get_index(tables,'业务种类','垫款标志')
        if len(payed_discount_index)>0:
            if '笔' in str(self.tables[payed_discount_index[0][0]]):
                payed_discount_keys = self.tables[payed_discount_index[0][0]][1]
                
                if  len(payed_bankdraf_index)>0:
                    payed_discount_data = self.tables[payed_discount_index[0][0]][2:payed_bankdraf_index[0][1]-1]
                else:
                    payed_discount_data = self.tables[payed_discount_index[0][0]][2:]
                
            else:
                payed_discount_keys = self.tables[payed_discount_index[0][0]][0]
                if  len(payed_bankdraf_index)>0:
                    payed_discount_data = self.tables[payed_discount_index[0][0]][1:payed_bankdraf_index[0][1]]
                else:
                    payed_discount_data = self.tables[payed_discount_index[0][0]]
            payed_discount_dict = [dict(zip(payed_discount_keys, values)) for values in payed_discount_data]  
            payed_discount_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in payed_discount_dict]
            
        else:
              payed_discount_dict =None 
        return payed_discount_dict

    #银行承兑和信用证
    def get_payed_bankdraft_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        payed_bankdraf_index = self.get_index(tables,'业务种类','垫款标志')
        license_index = self.get_index(tables,'许可部门','许可类型')
        if  len(payed_bankdraf_index)>0:
            payed_bankdraf_keys = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]]
            if len(license_index)>0 and license_index[0][0] == payed_bankdraf_index[0][0]:
                
                if len(payed_bankdraf_index)==1:
                    payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:license_index[0][1]]
                elif len(payed_bankdraf_index)==2:
                    if '笔' in str(self.tables[payed_bankdraf_index[0][0]]):
                        payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:payed_bankdraf_index[1][1]-1] + self.tables[payed_bankdraf_index[1][0]][payed_bankdraf_index[1][1]+1:license_index[0][1]]
                    else:
                        payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:payed_bankdraf_index[1][1]] + self.tables[payed_bankdraf_index[1][0]][payed_bankdraf_index[1][1]+1:license_index[0][1]]
            else:
                if len(payed_bankdraf_index)==1:
                    payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:]
                elif len(payed_bankdraf_index)==2:
                    if '笔' in str(self.tables[payed_bankdraf_index[0][0]]):
                        payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:payed_bankdraf_index[1][1]-1] + self.tables[payed_bankdraf_index[1][0]][payed_bankdraf_index[1][1]+1:]
                    else:
                        payed_bankdraf_data = self.tables[payed_bankdraf_index[0][0]][payed_bankdraf_index[0][1]+1:payed_bankdraf_index[1][1]] + self.tables[payed_bankdraf_index[1][0]][payed_bankdraf_index[1][1]+1:]
            payed_bankdraf_dict = [dict(zip(payed_bankdraf_keys, values)) for values in payed_bankdraf_data]
            payed_bankdraf_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in payed_bankdraf_dict]
            
            
        else:
            payed_bankdraf_dict =None 
        return payed_bankdraf_dict

    #相关还款责任明细(只有除贴现外的信贷还款责任，贴现和其他担保交易还款责任还没有)
    def get_liabillity_detail_data(self,report_info):
        if not self.tables:
            return None
        liabillity_detail_data_dicts=[]
        tables = self.tables
        liabillity_detail_index=self.get_index(tables,'保证合同编号','到期日')
        if len(liabillity_detail_index)>0:
            if len(liabillity_detail_index)==1:
                # if '笔' in str(tables[liabillity_detail_index[0][0]]):
                liabillity_detail_header = self.tables[liabillity_detail_index[0][0]][liabillity_detail_index[0][1]:3]
                liabillity_detail_data_rows = self.tables[liabillity_detail_index[0][0]][3:]
                flattened_liabillity_detail_header = [item for sublist in liabillity_detail_header for item in sublist]        
                for i in range(0,len(liabillity_detail_data_rows)//2):
                    liabillity_detail_start_index = i * 2
                    # print( payed_start_loan_index)
                    if  liabillity_detail_start_index<=len(liabillity_detail_data_rows):
                        liabillity_detail_data_set =  liabillity_detail_data_rows[liabillity_detail_start_index: liabillity_detail_start_index + 2]
                        # print(data_loan_set)
                        liabillity_detail_combined_data = [item for sublist in liabillity_detail_data_set for item in sublist]
                        liabillity_detail_dict = dict(zip(flattened_liabillity_detail_header, liabillity_detail_combined_data))
                        liabillity_detail_dict['报告编号'] = report_info.report_number
                        liabillity_detail_dict['统一社会信用代码'] =report_info.credit_code
                        liabillity_detail_data_dicts.append(liabillity_detail_dict)           
        else:
            liabillity_detail_data_dicts= None
        return liabillity_detail_data_dicts
    #非信贷记录明细
    #公用事业缴费信息
    def get_public_fee_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        public_fee_info_index = self.get_index(tables,'公用事业单位名称','业务类型')
        if len(public_fee_info_index)>0:
            public_fee_info_keys = self.tables[public_fee_info_index[0][0]][0]
            public_fee_info_data = self.tables[public_fee_info_index[0][0]][1:]
            public_fee_dict = [dict(zip(public_fee_info_keys, values)) for values in public_fee_info_data]
            public_fee_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in public_fee_dict ]
        
        else:
            public_fee_dict =None
        return public_fee_dict
    #附件
    #现在只提取银行承兑汇票和信用证明细，只提取他们的表格，表格上的银行信息不提取。
    #如何把表格上的信息和表格同时提取，还没找到很好的办法。
    #未结清借款历史表现中如果出现特别交易提示，会造成同种借款表格被分割成不同长度的表格，造成提取不完整。以后再修复（新疆普济堂公司）。
    def get_appendix_loan_detail(self,report_info):
        if not self.tables:
            return None
        appendix_loan_detail_dicts = []
        tables = self.tables
        appendix_loan_detail_index = self.get_index(tables,'余额变化日期','五级分类认定日期')
        if len(appendix_loan_detail_index)>0:
            remove_tables = self.remove_sublist_containing_text(tables, '特定交易提示')
            remove_tables = self.remove_sublist_containing_text(remove_tables, '交易类型')
            remove_tables = self.remove_sublist_containing_text(remove_tables, '提前还款')
         
            appendix_loan_detail_header = self.tables[appendix_loan_detail_index[0][0]][:appendix_loan_detail_index[0][1]+2]
            flattened_appendix_loan_detail_header = [item for sublist in appendix_loan_detail_header for item in sublist] 
            remove_tables = self.remove_sublist_containing_text(tables,'余额变化日期')
            remove_tables = self.remove_sublist_containing_text(remove_tables,'最近一次实际还款日期')
            appendix_loan_detail_data = remove_tables[appendix_loan_detail_index[0][0]]
            for i in range(0,len(appendix_loan_detail_data)//2):
                appendix_loan_detail_index_start = i * 2
                # print( payed_start_loan_index)
                if  appendix_loan_detail_index_start<=len(appendix_loan_detail_data):
                    appendix_loan_detail_data_set =  appendix_loan_detail_data[appendix_loan_detail_index_start: appendix_loan_detail_index_start  + 2]
                    appendix_loan_detail_data_combined = [item for sublist in appendix_loan_detail_data_set for item in sublist]
                    appendix_loan_detail_dict = dict(zip(flattened_appendix_loan_detail_header, appendix_loan_detail_data_combined))
                    appendix_loan_detail_dict['报告编号'] = report_info.report_number
                    appendix_loan_detail_dict['统一社会信用代码'] =report_info.credit_code
                    appendix_loan_detail_dicts.append(appendix_loan_detail_dict)           
            
        else:
            appendix_loan_detail_dicts = None
        return appendix_loan_detail_dicts

    #循环透支的历史表现
    def get_appendix_circle_detail(self,report_info):
        if not self.tables:
            return None
        appendix_circle_detail_dicts = []
        tables = self.tables
        appendix_circle_detail_index = self.get_index(tables,'最近一次约定还款日期','剩余还款月数')
        appendix_discount_index = self.get_index(tables,'贴现金额','信息报告日期')
        if len(appendix_circle_detail_index)>0:
            
            appendix_circle_detail_header = self.tables[appendix_circle_detail_index[0][0]][:appendix_circle_detail_index[0][1]+1]
            flattened_appendix_circle_detail_header = [item for sublist in appendix_circle_detail_header for item in sublist] 
            # print(flattened_appendix_circle_detail_header)
            remove_tables = self.remove_sublist_containing_text(tables,'五级分类认定日期')
            remove_tables = self.remove_sublist_containing_text(remove_tables,'剩余还款月数')
            if len(appendix_discount_index)>0:
                appendix_circle_detail_data = self.tables[appendix_circle_detail_index[0][0]][:appendix_discount_index[0][1]-1]
            else:
                appendix_circle_detail_data = remove_tables[appendix_circle_detail_index[0][0]]
            # print(appendix_circle_detail_data)
            for i in range(0,len(appendix_circle_detail_data)//2):
                appendix_circle_detail_index_start = i * 2
                # print( payed_start_circle_index)
                if  appendix_circle_detail_index_start<=len(appendix_circle_detail_data):
                    appendix_circle_detail_data_set =  appendix_circle_detail_data[appendix_circle_detail_index_start: appendix_circle_detail_index_start  + 2]
                    appendix_circle_detail_data_combined = [item for sublist in appendix_circle_detail_data_set for item in sublist]
                    appendix_circle_detail_dict = dict(zip(flattened_appendix_circle_detail_header, appendix_circle_detail_data_combined))
                    appendix_circle_detail_dict['报告编号'] = report_info.report_number
                    appendix_circle_detail_dict['统一社会信用代码'] =report_info.credit_code
                    appendix_circle_detail_dicts.append(appendix_circle_detail_dict)           
            
        else:
            appendix_circle_detail_dicts = None
        return appendix_circle_detail_dicts

    # appendix_circle_detail_dicts = get_appendix_circle_detail(tables,report_info)

    #银行承兑未结清
    def get_appendix_bankdraft_letter_detail(self,report_info):
        if not self.tables:
            return None
        appendix_bankdraft_letter_dicts = []
        tables = self.tables
        appendix_bankdraft_letter_index = self.get_index(tables,'保证金比例','风险敞口')
        if len(appendix_bankdraft_letter_index)>0:
            
            appendix_bankdraft_letter_header = self.tables[appendix_bankdraft_letter_index[0][0]][:appendix_bankdraft_letter_index[0][1]+1]
            flattened_appendix_bankdraft_letter_header = [item for sublist in appendix_bankdraft_letter_header for item in sublist] 
            remove_tables = self.remove_sublist_containing_text(tables,'保证金比例')
            remove_tables = self.remove_sublist_containing_text(remove_tables,'反担保方式')
            appendix_bankdraft_letter_data = remove_tables[appendix_bankdraft_letter_index[0][0]]
            for i in range(0,len(appendix_bankdraft_letter_data)//2):
                appendix_bankdraft_letter_index_start = i * 2
                # print( payed_start_loan_index)
                if  appendix_bankdraft_letter_index_start<=len(appendix_bankdraft_letter_data):
                    appendix_bankdraft_letter_data_set =  appendix_bankdraft_letter_data[appendix_bankdraft_letter_index_start: appendix_bankdraft_letter_index_start  + 2]
                    appendix_bankdraft_letter_data_combined = [item for sublist in appendix_bankdraft_letter_data_set for item in sublist]
                    appendix_bankdraft_letter_dict = dict(zip(flattened_appendix_bankdraft_letter_header, appendix_bankdraft_letter_data_combined))
                    appendix_bankdraft_letter_dict['报告编号'] = report_info.report_number
                    appendix_bankdraft_letter_dict['统一社会信用代码'] =report_info.credit_code
                    appendix_bankdraft_letter_dicts.append(appendix_bankdraft_letter_dict)           
            
        else:
            appendix_bankdraft_letter_dicts = None
        return appendix_bankdraft_letter_dicts


    #公共记录明细
    #欠税记录
    def get_owed_taxes_data(self,report_info):
        if not self.tables:
            return None
        tables = self.tables
        owed_taxes_index = self.get_index(tables,'主管税务机关','欠税统计日期')
        if len(owed_taxes_index)>0:
            owed_taxes_keys = self.tables[owed_taxes_index[0][0]][owed_taxes_index[0][1]]
            owed_taxes_data = self.tables[owed_taxes_index[0][0]][owed_taxes_index[0][1]+1:]
            owed_taxes_dict = [dict(zip(owed_taxes_keys, values)) for values in owed_taxes_data]
            owed_taxes_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in owed_taxes_dict]
        
        else:
            owed_taxes_dict =None
        return owed_taxes_dict

    #获得许可记录
    def get_license_data(self,report_info):
        tables = self.tables
        license_index = self.get_index(tables,'许可部门','许可类型')
        if len(license_index)>0:
            license_keys = self.tables[license_index[0][0]][license_index[0][1]]
            license_data = self.tables[license_index[0][0]][license_index[0][1]+1:]
            license_dict = [dict(zip(license_keys, values)) for values in license_data]
            license_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in license_dict]
        else:
            license_dict =None    
        return license_dict
    def get_certification_data(self,report_info):
        tables = self.tables
        certification_index = self.get_index(tables,'认证部门','认证类型')
        if len(certification_index)>0:
            certification_keys = self.tables[certification_index[0][0]][certification_index[0][1]]
            certification_data = self.tables[certification_index[0][0]][certification_index[0][1]+1:]
            certification_dict = [dict(zip(certification_keys, values)) for values in certification_data]
            certification_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in certification_dict]
        else:
            certification_dict =None 
        return certification_dict
    #获得认证记录

    #获得资质记录
    def get_qualification_data(self,report_info):
        tables = self.tables
        Qualification_index = self.get_index(tables,'认定部门','资质类型')
        if len(Qualification_index)>0:
            Qualification_keys = self.tables[Qualification_index[0][0]][Qualification_index[0][1]]
            Qualification_data = self.tables[Qualification_index[0][0]][Qualification_index[0][1]+1:]
            Qualification_dict = [dict(zip(Qualification_keys, values)) for values in Qualification_data]
            Qualification_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in Qualification_dict]
        else:
            Qualification_dict =None 
        return Qualification_dict

    #获得奖励记录
    def get_award_data(self,report_info):
        tables = self.tables
        award_index = self.get_index(tables,'奖励部门','奖励名称')
        if len(award_index)>0:
            award_keys = self.tables[award_index[0][0]][award_index[0][1]]
            award_data = self.tables[award_index[0][0]][award_index[0][1]+1:]
            award_dict = [dict(zip(award_keys, values)) for values in award_data]
            award_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in award_dict]
        else:
            award_dict =None
        return award_dict


    #出入境检验检疫绿色通道信息
    def get_approve_data(self,report_info):
        tables = self.tables
        approve_index = self.get_index(tables,'批准部门','出口商品名称')
        if len(approve_index)>0:
            approve_keys = self.tables[approve_index[0][0]][approve_index[0][1]]
            approve_data = self.tables[approve_index[0][0]][approve_index[0][1]+1:]
            approve_dict = [dict(zip(approve_keys, values)) for values in approve_data]
            approve_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in approve_dict]
        else:
            approve_dict =None 
        return approve_dict


    #进出口商品免检信息
    def get_no_check_data(self,report_info):
        tables = self.tables
        no_check_index = self.get_index(tables,'批准部门','免验商品名称')
        if len(no_check_index)>0:
            no_check_keys = self.tables[no_check_index[0][0]][no_check_index[0][1]]
            no_check_data = self.tables[no_check_index[0][0]][no_check_index[0][1]+1:]
            no_check_dict = [dict(zip(no_check_keys, values)) for values in no_check_data]
            no_check_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in no_check_dict]
        else:
            no_check_dict =None
        return no_check_dict
    #专利情况
    def get_patent_data(self,report_info):
        tables = self.tables
        patent_index = self.get_index(tables,'专利名称','专利号')
        if len(patent_index)>0:
            patent_keys = self.tables[patent_index[0][0]][patent_index[0][1]]
            patent_data = self.tables[patent_index[0][0]][patent_index[0][1]+1:]
            patent_dict = [dict(zip(patent_keys, values)) for values in patent_data]
            patent_dict = [{**item, '报告编号': report_info.report_number, '统一社会信用代码': report_info.credit_code} for item in patent_dict]
        else:
            patent_dict =None 
        return patent_dict

def get_titles(report_info):   
    # print('report_info',report_info)
    if  'company_name' in report_info:
          data_titles = [
          '企业基本信息', '股东信息', '管理者信息', '信息概要', '信息概要交易信息', '负面信息概要', 
          '未结清负面信息概要', '未结清账户信息概要', '未结清循环额度信息', '相关还款责任概要',
          '已结清负面信息概要', '已结清账户信息概要', '被追偿业务明细', '未结清借款明细', '未结清循环透支信息',
          '未结清贴现明细', '未结清信用证明细', '相关还款责任明细', '授信信息', '已结清借款明细', 
          '已结清贴现明细', '已结清承兑汇票', '附件_未结清_借款历史表现', '附件_未结清_循环透支历史表现',
          '附件_未结清_银行承兑和信用证明细', '公共事业缴费信息', '欠税信息', '许可证信息', '认证信息',
          '相关资质信息', '奖励信息', '出入境检验检疫', '出口免检信息', '专利信息'
        ]    
          file_name = report_info['company_name']
    elif  '被查询者姓名' in report_info:
        data_titles = ['报告信息','身份信息','地址信息','职业信息','账户信息','被追偿信息','呆账信息','逾期信息',
                   '信贷概要信息','还款责任信息','后付费欠费信息','查询概要信息','还款责任明细',
                  '授信明细','后付费明细','欠税记录','行政处罚记录','公积金参缴记录',
                  '低保救助信息','认证信息','惩戒类信息','查询明细']
        file_name = report_info['被查询者姓名']
    else:
        
        data_titles = ['基础信息','负债信息','查询信息','对外担保信息','信用卡信息','借款信息']
        if isinstance(report_info, list):
            file_name = report_info[0].get('姓名')
        else:
            file_name = report_info.get('姓名')
    return  data_titles,file_name
class ExcelWriter:
    @staticmethod
    def to_excel(path, data_list, report_info):
        data_titles,file_name = get_titles(report_info)
        if len(data_titles) != len(data_list):
            raise ValueError("The lengths of data_titles and data_list do not match.")

        if isinstance(path, BytesIO):
            custom_excel_writer = ot.CustomExcelWriter(path)
        else:
            output_path = os.path.join(os.path.dirname(path), f"{file_name}.xlsx")
            
            custom_excel_writer = ot.CustomExcelWriter(output_path)

        for title, data in zip(data_titles, data_list):
            try:
                custom_excel_writer.add_sheet(title, data, title="", header = True,start_col=2, borders="medium")
            except Exception as e:
                logging.error(f"Error adding sheet '{title}': {e}")

        try:
            custom_excel_writer.save()
        except Exception as e:
            logging.error(f"Error saving Excel file: {e}")
#个人征信自查版简版解析程序
class CR_PSParser:
    def __init__(self, path):
        self.path = path
        self.parse = cp.PDFExtractor(path)
        self.text = self.parse.extract_text()
        self.tables = self.parse.extract_tables()

    def extract_between(self, long_string, A, B):
        start_index = long_string.find(A)
        if start_index == -1:
            return None
        start_index += len(A)
        end_index = long_string.find(B, start_index)
        if end_index == -1:
            return None
        return long_string[start_index:end_index]

    def clean_text(self, text):
        temp_text = re.sub(r'第 \d+ 页，共 \d+ 页', '', text)
        if '贷记卡' in temp_text:
            drop_text = temp_text.replace('发生过逾期的贷记卡账户明细如下：', '').replace('从未逾期过的贷记卡及透支未超过60天的准贷记卡账户明细如下：','')
            cleaned_text = re.sub(r'(?<!。)\n', '', drop_text)
        elif '贷款' in temp_text and '查询' not in temp_text:
            drop_text = temp_text.replace('发生过逾期的账户明细如下：', '').replace('从未','')
            cleaned_text = re.sub(r'(?<!。)\n', '', drop_text)
        elif '查询记录' in temp_text:
            cleaned_text = []
            drop_text = temp_text.replace('这部分包含您的信用报告最近2年内被查询的记录。','').replace('机构查询记录明细','').replace('个人查询记录明细','')
            for line in drop_text.splitlines():
                if len(line) > 10:
                    cleaned_text.append(line)
        return cleaned_text
    
    def extract_base_info(self,text):
        lines=text.splitlines()
        temp = lines[1].split('：')
        report_date = temp[2]
        report_num = temp[1].split(' ')[0]
        temp_1 = lines[2].split('：')
        name = temp_1[1].split(' ')[1]
        identility = temp_1[3].split(' ')[0]
        marry = temp_1[3].split(' ')[1]
        
        birthdate_str = identility[6:14]  
        birthdate = datetime.strptime(birthdate_str, '%Y%m%d')
        parse_date = datetime.today()
        age = parse_date.year - birthdate.year - ((parse_date.month, parse_date.day) < (birthdate.month, birthdate.day))
    
        info = [{"报告日期":report_date,
                "报告编号":report_num,
                "姓名":name,
                "证件号码":identility,
                "年龄":age,
                "婚姻":marry,
                "解析日期":parse_date}]
        return info
    def extract_card_info(self, text):
        patterns = {
            '发卡日期': re.compile(r'(?P<发卡日期>\d{4}年\d{2}月\d{2}日)'),
            '金融机构': re.compile(r'(?P<金融机构>[\u4e00-\u9fa5]+(?:股份有限公司|有限责任公司|有限公司)[\u4e00-\u9fa5]*)'),
            '货币种类': re.compile(r'（(?P<货币种类>[\u4e00-\u9fa5]+账户)'),
            '卡号尾号': re.compile(r'卡片尾号：(?P<卡号尾号>\d{4})'),
            '授信额度': re.compile(r'信用额度(?P<授信额度>[\d,]+)'),
            '已用额度': re.compile(r'已使用额度(?P<已用额度>[\d,]+)'),
            '余额': re.compile(r'余额(?P<余额>[\d,]+)')
        }

        results = []
        for line in text.splitlines():
            # Initialize info dictionary with None for each key
            info = {key: None for key in patterns.keys()}

            # Match each pattern separately
            for key, pattern in patterns.items():
                match = pattern.search(line)
                if match:
                    info[key] = match.group(key)

            # Clean the 金融机构 name if it was extracted
            if info['金融机构']:
                info['金融机构'] = self._clean_card_bank_name(info['金融机构'])

            # Determine account status using string search
            info.update(self._determine_card_status(line))

            results.append(info)
        return results

    def extract_loan_info(self, text):
        patterns = {
            '借款日期': re.compile(r'(?P<借款日期>\d{4}年\d{2}月\d{2}日)'),
            '金融机构': re.compile(r'(?P<金融机构>[\u4e00-\u9fa5]+(?:\（[\u4e00-\u9fa5]+\）)?(?:股份有限公司|有限责任公司|有限公司|股份公司)[\u4e00-\u9fa5]*)'),
            '借款金额': re.compile(r'(?P<借款金额>[\d,]+)元（人民币）'),
            '授信额度': re.compile(r'信用额度(?P<授信额度>[\d,]+)元（人民币）'),
            '到期日': re.compile(r'额度有效期至(?P<到期日>\d{4}年\d{2}月\d{2}日)'),
            '余额': re.compile(r'余额(?:为)?(?P<余额>[\d,]+)'),
            '借款种类': re.compile(r'发放的[\d,]+元（人民币）(?P<借款种类>[\u4e00-\u9fa5]+贷款)')
        }

        results = []
        for line in text.splitlines():
            # Initialize info dictionary with None for each key
            info = {key: None for key in patterns.keys()}

            # Match each pattern separately
            for key, pattern in patterns.items():
                match = pattern.search(line)
                if match:
                    info[key] = match.group(key)

            # Clean the bank name if it was extracted
            if info['金融机构']:
                info['金融机构'] = self._clean_loan_bank_name(info['金融机构'])

            # Determine loan status using string search
            info.update(self._determine_loan_status(line))

            results.append(info)
        return results
    def extract_liability_info(self, text):
        patterns = {
            '担保日期': re.compile(r'(?P<担保日期>\d{4}年\d{2}月\d{2}日)'),
            '被担保人': re.compile(r'为(?P<被担保人>[\u4e00-\u9fa5]+)（'),
            '被担保人证件号码': re.compile(r'证件号码：(?P<被担保人证件号码>\w+)'),
            '放款机构': re.compile(r'在(?P<放款机构>[\u4e00-\u9fa5]+银行股份有限公司[\u4e00-\u9fa5]+)'),
            '责任类型': re.compile(r'责任人类型为(?P<责任类型>[\u4e00-\u9fa5]+)'),
            '责任金额': re.compile(r'相关还款责任金额(?P<责任金额>[\d,]+|--)'),
            '担保余额': re.compile(r'贷款余额(?P<担保余额>[\d,]+)')
        }
        results = []
        for line in text.splitlines():
            # Initialize info dictionary with None for each key
            info = {key: None for key in patterns.keys()}

            # Match each pattern separately
            for key, pattern in patterns.items():
                match = pattern.search(line)
                if match:
                    info[key] = match.group(key)

            results.append(info)
        return results

    # def _extract_info(self, text, patterns, status_func=None, bank_clean_func=None):
    #     results = []
    #     for line in text.splitlines():
    #         info = {key: (match.group(key) if match else None) for key, pattern in patterns.items() if (match := pattern.search(line))}
    #         if bank_clean_func and 'bank' in info and info['bank']:
    #             info['bank'] = bank_clean_func(info['bank'])
    #         if status_func:
    #             info.update(status_func(line))
    #         results.append(info)
    #     return results

    def _clean_card_bank_name(self, bank_name):
        return bank_name.replace('日', '').replace('发放的贷记卡', '')

    def _clean_loan_bank_name(self, bank_name):
        return bank_name.replace('日', '').replace('发放的', '').split('为')[0]

    def _determine_card_status(self, line):
        if '销户' in line:
            return {'账户状态': '销户'}
        elif '呆账' in line:
            return {'账户状态': '呆账'}
        elif '当前有逾期' in line:
            return {'账户状态': '逾期'}
        else:
            return {'账户状态': '正常'}

    def _determine_loan_status(self, line):
        if '当前有逾期' in line:
            return {'借款状态': '逾期'}
        elif '已结清' in line:
            return {'借款状态': '结清'}
        else:
            return {'借款状态': '正常'}

    def extract_query_info(self, text):
        query_temp_text = [line.split() for line in text]
        query_column = query_temp_text[0]
        query_data = query_temp_text[1:]
        query_df = pd.DataFrame(query_data, columns=query_column)
        return query_df[~query_df.apply(lambda row: row.astype(str).str.contains('编号').any(), axis=1)]
def summarize_status(statuses):
    if statuses.isin(['逾期']).any():
        return '逾期'
    if statuses.isin(['呆账']).any():
        return '呆账'
    return '正常' 
#个人征信自查版详版解析程序
class CR_PDParser:
    def __init__(self, path: str):
        self.path = path
        self.extractor = cp.PDFExtractor(path)
        self.text = self.extractor.extract_text(1)
        self.tables = self.extractor.extract_tables()

    @staticmethod
    def get_index(data: list, ob_str_1: str, ob_str_2: str = None, start_i: int = 0, end_i: int = None, start_j: int = 0, end_j: int = None):
        index_list = []
        end_i = end_i if end_i is not None else len(data)
        for i in range(start_i, min(end_i, len(data))):
            sublist = data[i]
            end_j_local = end_j if end_j is not None else len(sublist)
            for j in range(start_j, min(end_j_local, len(sublist))):
                subsublist = sublist[j]
                if (subsublist is not None) and (ob_str_1 in subsublist) and (ob_str_2 is None or ob_str_2 in subsublist):
                    index_list.append((i, j))
        return index_list

    def extract_report_info(self):
        if not self.tables or len(self.tables[0]) < 3:
            return None
        info = {}
        keys = self.tables[0][1]
        values = self.tables[0][2]
        for key, value in zip(keys, values):
            info[key] = value
        info['report_number'] = self.tables[0][0][0].split('：')[1]
        info['report_date'] = self.tables[0][0][3].split('：')[1]
        return info

    def extract_id_info(self):
        sex_index = self.get_index(self.tables, '性别')
        spouse_index = self.get_index(self.tables[sex_index[0][0]], '姓名')
        return {
            "性别": self.tables[sex_index[0][0]][1][0],
            "出生日期": self.tables[sex_index[0][0]][1][2],
            "婚姻状况": self.tables[sex_index[0][0]][1][3],
            "就业状况": self.tables[sex_index[0][0]][1][4],
            "学历": self.tables[sex_index[0][0]][5][0],
            "学位": self.tables[sex_index[0][0]][5][2],
            "国籍": self.tables[sex_index[0][0]][5][3],
            "电子邮箱": self.tables[sex_index[0][0]][5][4],
            "通讯地址": self.tables[sex_index[0][0]][9][0],
            "户籍地址": self.tables[sex_index[0][0]][9][3],
            "手机号码": self.tables[sex_index[0][0]][13][1],
            "信息更新日期": self.tables[sex_index[0][0]][13][3],
            "数据发生机构名称": self.tables[sex_index[0][0]][3][0],
            "配偶姓名": self.tables[sex_index[0][0]][spouse_index[0][0] + 1][0],
            "配偶证件类型": self.tables[sex_index[0][0]][spouse_index[0][0] + 1][1],
            "配偶证件号码": self.tables[sex_index[0][0]][spouse_index[0][0] + 1][2],
            "配偶工作单位": self.tables[sex_index[0][0]][spouse_index[0][0] + 1][3],
            "配偶联系电话": self.tables[sex_index[0][0]][spouse_index[0][0] + 1][4],
        }

    def extract_addr_info(self):
        addr_index = self.get_index(self.tables, '居住地址')
        if addr_index:
            addr_index_index = self.get_index(self.tables[addr_index[0][0]], '编号')
            addr_columns = self.tables[addr_index[0][0]][addr_index[0][1]]
            addr_other_column = self.tables[addr_index[0][0]][addr_index_index[-1][0]]
            if addr_index_index[-1][0] >= addr_index[0][1]:
                addr_data = self.tables[addr_index[0][0]][addr_index[0][1] + 1:addr_index_index[-1][0]]
                addr_data_other = self.tables[addr_index[0][0]][addr_index_index[-1][0] + 1:]
                addr_data_info = pd.DataFrame(addr_data_other, columns=addr_other_column)
                addr_info = pd.DataFrame(addr_data, columns=addr_columns)
                addr_info = pd.merge(addr_info, addr_data_info)
                addr_info = addr_info.dropna(axis=1)
            else:
                addr_info = None
        else:
            addr_info = None
        return addr_info

    def extract_career_info(self):
        career_index = self.get_index(self.tables, '单位性质')
        if career_index:
            career_index_index = self.get_index(self.tables[career_index[0][0]], '编号')
            career_column = self.tables[career_index[0][0]][career_index_index[0][0]]
            career_column_1 = self.tables[career_index[0][0]][career_index_index[1][0]]
            career_column_2 = self.tables[career_index[0][0]][career_index_index[2][0]]
            career_data = self.tables[career_index[0][0]][career_index_index[0][0] + 1:career_index_index[1][0]]
            career_data_1 = self.tables[career_index[0][0]][career_index_index[1][0] + 1:career_index_index[2][0]]
            career_data_2 = self.tables[career_index[0][0]][career_index_index[2][0] + 1:]
            career_df = pd.DataFrame(career_data, columns=career_column)
            career_df_1 = pd.DataFrame(career_data_1, columns=career_column_1)
            career_df_2 = pd.DataFrame(career_data_2, columns=career_column_2)
            career_info = pd.merge(career_df, career_df_1, on='编号')
            career_info = pd.merge(career_info, career_df_2, on='编号')
            career_info = career_info.dropna(axis=1)
        else:
            career_info = None
        return career_info

    def extract_account_info(self):
        account_index = self.get_index(self.tables, '首笔业务发放月份')
        if account_index:
            account_columns = ['业务大类', '业务小类', '账户数', '首笔业务发放月份']
            account_data = self.tables[account_index[0][0]][1:-1]
            account_info = pd.DataFrame(account_data, columns=account_columns)
            account_info = account_info.ffill(axis=0)
        else:
            account_info = None
        return account_info

    def extract_recovered_account(self):
        recovered_index = self.get_index(self.tables, '被追偿信息汇总')
        if recovered_index:
            recovered_column = self.tables[recovered_index[0][0]][1]
            recovered_data = self.tables[recovered_index[0][0]][2:]
            recovered_account = pd.DataFrame(recovered_data, columns=recovered_column)
            recovered_account = recovered_account.dropna(axis=1)
        else:
            recovered_account = None
        return recovered_account

    def extract_baddebt_account(self):
        baddebt_index = self.get_index(self.tables, '呆账信息汇总')
        if baddebt_index:
            baddebt_column = self.tables[baddebt_index[0][0]][1]
            baddebt_data = self.tables[baddebt_index[0][0]][2:]
            baddebt_account = pd.DataFrame(baddebt_data, columns=baddebt_column)
            baddebt_account = baddebt_account.dropna(axis=1)
        else:
            baddebt_account = None
        return baddebt_account

    def extract_overdue_account(self):
        overdue_account_index = self.get_index(self.tables, '单月最高逾期/透支总额')
        if overdue_account_index:
            credit_index = self.get_index(self.tables[overdue_account_index[0][0]], '授信总额')
            overdue_account_column = self.tables[overdue_account_index[0][0]][overdue_account_index[0][1]]
            if credit_index:
                overdue_account_data = self.tables[overdue_account_index[0][0]][overdue_account_index[0][1] + 1:credit_index[0][0] - 1]
            else:
                overdue_account_data = self.tables[overdue_account_index[0][0]][overdue_account_index[0][1] + 1:-1]
            overdue_account = pd.DataFrame(overdue_account_data, columns=overdue_account_column)
            overdue_account = overdue_account.dropna(axis=1)
        else:
            overdue_account = None
        return overdue_account

    def extract_loan_summary(self):
        loan_summary = {}
        uncircle_account_index = self.get_index(self.tables, '非循环贷账户信息汇总')
        if uncircle_account_index:
            uncircle_column = self.tables[uncircle_account_index[0][0]][uncircle_account_index[0][1] + 1]
            uncircle_data = self.tables[uncircle_account_index[0][0]][uncircle_account_index[0][1] + 2]
            uncircle_loan = pd.DataFrame(data=[uncircle_data], columns=uncircle_column)
            uncircle_loan = uncircle_loan.dropna(axis=1)
            uncircle_loan['账户类型'] = '非循环贷账户'
            loan_summary['非循环贷账户'] = uncircle_loan
        else:
            loan_summary['非循环贷账户'] = None

        circle_1_account_index = self.get_index(self.tables, '循环贷账户一信息汇总')
        if circle_1_account_index:
            circle_1_column = self.tables[circle_1_account_index[0][0]][circle_1_account_index[0][1] + 1]
            circle_1_data = self.tables[circle_1_account_index[0][0]][circle_1_account_index[0][1] + 2]
            circle_1_loan = pd.DataFrame(data=[circle_1_data], columns=circle_1_column)
            circle_1_loan = circle_1_loan.dropna(axis=1)
            circle_1_loan['账户类型'] = '循环贷账户一'
            loan_summary['循环贷账户一'] = circle_1_loan
        else:
            loan_summary['循环贷账户一'] = None

        circle_2_account_index = self.get_index(self.tables, '循环贷账户二信息汇总')
        if circle_2_account_index:
            circle_2_column = self.tables[circle_2_account_index[0][0]][circle_2_account_index[0][1] + 1]
            circle_2_data = self.tables[circle_2_account_index[0][0]][circle_2_account_index[0][1] + 2]
            circle_2_loan = pd.DataFrame(data=[circle_2_data], columns=circle_2_column)
            circle_2_loan = circle_2_loan.dropna(axis=1)
            circle_2_loan['账户类型'] = '循环贷账户二'
            loan_summary['循环贷账户二'] = circle_2_loan
        else:
            loan_summary['循环贷账户二'] = None

        creditcard_account_index = self.get_index(self.tables, '贷记卡账户信息汇总')
        if creditcard_account_index:
            creditcard_column = self.tables[creditcard_account_index[0][0]][creditcard_account_index[0][1] + 1]
            creditcard_data = self.tables[creditcard_account_index[0][0]][creditcard_account_index[0][1] + 2]
            creditcard_loan = pd.DataFrame(data=[creditcard_data], columns=creditcard_column)
            creditcard_loan = creditcard_loan.dropna(axis=1)
            creditcard_loan['账户类型'] = '贷记卡账户'
            loan_summary['贷记卡账户'] = creditcard_loan
        else:
            loan_summary['贷记卡账户'] = None

        quasi_creditcard_account_index = self.get_index(self.tables, '准贷记卡账户信息汇总')
        if quasi_creditcard_account_index:
            quasi_creditcard_column = self.tables[quasi_creditcard_account_index[0][0]][quasi_creditcard_account_index[0][1] + 1]
            quasi_creditcard_data = self.tables[quasi_creditcard_account_index[0][0]][quasi_creditcard_account_index[0][1] + 2]
            quasi_creditcard_loan = pd.DataFrame(data=[quasi_creditcard_data], columns=quasi_creditcard_column)
            quasi_creditcard_loan = quasi_creditcard_loan.dropna(axis=1)
            quasi_creditcard_loan['账户类型'] = '准贷记卡账户'
            loan_summary['准贷记卡账户'] = quasi_creditcard_loan
        else:
            loan_summary['准贷记卡账户'] = None

        return loan_summary

    def extract_liabillity_account(self):
        liabillity_account_index = self.get_index(self.tables, '相关还款责任信息汇总')
        if liabillity_account_index:
            liabillity_account_dict = {
                "为个人": {
                    "担保责任": {
                        "账户数": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][0],
                        "担保金额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][2],
                        "余额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][3]
                    },
                    "其他相关还款责任": {
                        "账户数": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][4],
                        "担保金额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][5],
                        "余额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 4][6]
                    }
                },
                "为企业": {
                    "担保责任": {
                        "账户数": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][0],
                        "担保金额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][2],
                        "余额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][3]
                    },
                    "其他相关还款责任": {
                        "账户数": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][4],
                        "担保金额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][5],
                        "余额": self.tables[liabillity_account_index[0][0]][liabillity_account_index[0][1] + 8][6]
                    }
                }
            }
        else:
            liabillity_account_dict = None
        return liabillity_account_dict

    def extract_postpaid_info(self):
        postpaid_index = self.get_index(self.tables, '后付费业务欠费信息汇总')
        public_index = self.get_index(self.tables, '公共信息汇总')
        if postpaid_index:
            postpaid_column = self.tables[postpaid_index[0][0]][postpaid_index[0][1] + 1]
            if public_index:
                postpaid_data = self.tables[postpaid_index[0][0]][postpaid_index[0][1] + 2:public_index[0][1]]
                public_column = self.tables[public_index[0][0]][public_index[0][1] + 1]
                public_data = self.tables[public_index[0][0]][public_index[0][1] + 2:]
            else:
                postpaid_data = self.tables[postpaid_index[0][0]][postpaid_index[0][1] + 2:]
                public_data = []
            postpaid_info = pd.DataFrame(postpaid_data, columns=postpaid_column)
            public_info = pd.DataFrame(public_data, columns=public_column)
            postpaid_info = postpaid_info.dropna(axis=1)
            public_info = public_info.dropna(axis=1)
        else:
            postpaid_info = None
            public_info = None
        return postpaid_info, public_info

    def extract_query_summary(self):
        query_summary_index = self.get_index(self.tables, '最近1个月内的查询机构数')
        if query_summary_index:
            query_summary_dict = {
            "最近1个月内的查询机构数": {
                "贷款审批": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][0],
                "信用卡审批": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][1]
            },
            "最近1个月内的查询次数": {
                "贷款审批": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][2],
                "信用卡审批": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][3],
                "本人查询": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][4]
            },
            "最近2年内的查询次数": {
                "贷后管理": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][5],
                "担保资格审查": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][6],
                "特约商户": self.tables[query_summary_index[0][0]][query_summary_index[0][1] + 2][7]
            }
        }
        else:
            query_summary_dict = None
        return query_summary_dict

    def extract_liabillity_detail(self):
        liabillity_detail_index = self.get_index(self.tables, '保证合同编号')
        liabillity_detail_column = ['管理机构', '业务种类', '开立日期', '到期日期', '责任人类型', '还款责任金额', '币种', '保证合同编号', '主业务借款人', '主业务借款人证件类型', '主业务借款人证件号码', '截至日期', '余额', '五级分类', '还款状态/逾期月数']
        all_liabillity_detail_data = []
        if liabillity_detail_index:
            for i in range(len(liabillity_detail_index)):
                liabillity_detail_data = self.tables[liabillity_detail_index[i][0]][liabillity_detail_index[i][1] + 1] + self.tables[liabillity_detail_index[i][0]][liabillity_detail_index[i][1] + 3] + self.tables[liabillity_detail_index[i][0]][liabillity_detail_index[i][1] + 4] + self.tables[liabillity_detail_index[i][0]][liabillity_detail_index[i][1] + 6]
                liabillity_detail_data = [item for item in liabillity_detail_data if item is not None]
                if len(liabillity_detail_data) >= len(liabillity_detail_column):
                    liabillity_detail_data = [liabillity_detail_data[j:j + len(liabillity_detail_column)] for j in range(0, len(liabillity_detail_data), len(liabillity_detail_column))]
                    all_liabillity_detail_data.extend(liabillity_detail_data)
                else:
                    print("Insufficient data to match the columns")
            if all_liabillity_detail_data:
                liabillity_detail_df = pd.DataFrame(all_liabillity_detail_data, columns=liabillity_detail_column)
            else:
                liabillity_detail_df = None
        else:
            liabillity_detail_df = None
        return liabillity_detail_df

    def extract_credit_detail(self):
        credit_detail_index = self.get_index(self.tables, '授信额度用途')
        all_credit_detail_data = []
        if credit_detail_index:
            for i in range(len(credit_detail_index)):
                credit_detail_column = self.tables[credit_detail_index[i][0]][credit_detail_index[i][1]] + self.tables[credit_detail_index[i][0]][credit_detail_index[i][1] + 2]
                credit_detail_data = self.tables[credit_detail_index[i][0]][credit_detail_index[i][1] + 1] + self.tables[credit_detail_index[i][0]][credit_detail_index[i][1] + 3]
                credit_detail_data = [item for item in credit_detail_data if item is not None]
                if len(credit_detail_data) >= len(credit_detail_column):
                    credit_detail_data = [credit_detail_data[j:j + len(credit_detail_column)] for j in range(0, len(credit_detail_data), len(credit_detail_column))]
                    all_credit_detail_data.extend(credit_detail_data)
                else:
                    print("Insufficient data to match the columns")
            if all_credit_detail_data:
                credit_detail_df = pd.DataFrame(all_credit_detail_data, columns=credit_detail_column)
                credit_detail_df = credit_detail_df.dropna(axis=1)
            else:
                credit_detail_df = None
        else:
            credit_detail_df = None
        return credit_detail_df

    def extract_postpaid_detail(self):
        postpaid_detail_index = self.get_index(self.tables, '当前缴费状态')
        all_postpaid_detail_data = []
        if postpaid_detail_index:
            for i in range(len(postpaid_detail_index)):
                try:
                    postpaid_detail_column = self.tables[postpaid_detail_index[i][0]][postpaid_detail_index[i][1]]
                    postpaid_detail_data = self.tables[postpaid_detail_index[i][0]][postpaid_detail_index[i][1] + 1]
                    postpaid_detail_data = [item for item in postpaid_detail_data if item is not None]
                    if len(postpaid_detail_data) >= len(postpaid_detail_column):
                        postpaid_detail_data = [postpaid_detail_data[j:j + len(postpaid_detail_column)] for j in range(0, len(postpaid_detail_data), len(postpaid_detail_column))]
                        all_postpaid_detail_data.extend(postpaid_detail_data)
                    else:
                        print("Insufficient data to match the columns")
                except Exception as e:
                    print(e)
                    break
            if all_postpaid_detail_data:
                postpaid_detail_df = pd.DataFrame(all_postpaid_detail_data, columns=postpaid_detail_column)
                postpaid_detail_df = postpaid_detail_df.dropna(axis=1)
            else:
                postpaid_detail_df = None
        else:
            postpaid_detail_df = None
        return postpaid_detail_df

    def extract_tax_detail(self):
        tax_detail_index = self.get_index(self.tables, '欠税总额')
        if tax_detail_index:
            tax_detail_column = self.tables[tax_detail_index[0][0]][tax_detail_index[0][1]]
            tax_detail_data = self.tables[tax_detail_index[0][0]][tax_detail_index[0][1] + 1:]
            tax_detail_data = [item for item in tax_detail_data if item is not None]
            tax_detail_df = pd.DataFrame(tax_detail_data, columns=tax_detail_column)
            tax_detail_df = tax_detail_df.dropna(axis=1)
        else:
            tax_detail_df = None
        return tax_detail_df

    def extract_punishment_detail(self):
        punishment_detail_index = self.get_index(self.tables, '处罚机构')
        if punishment_detail_index:
            punishment_detail_column = self.tables[punishment_detail_index[0][0]][punishment_detail_index[0][1]]
            punishment_detail_data = self.tables[punishment_detail_index[0][0]][punishment_detail_index[0][1] + 1:]
            punishment_detail_data = [item for item in punishment_detail_data if item is not None]
            punishment_detail_df = pd.DataFrame(punishment_detail_data, columns=punishment_detail_column)
            punishment_detail_df = punishment_detail_df.dropna(axis=1)
        else:
            punishment_detail_df = None
        return punishment_detail_df

    def extract_fund_detail(self):
        fund_detail_index = self.get_index(self.tables, '参缴地')
        fund_detail_column = ['参缴地', '参缴日期', '初缴月份', '缴至月份', '参缴状态', '月缴存额', '个人缴存比例', '单位缴存比例', '缴费单位', '信息更新日期']
        all_fund_detail_data = []
        if fund_detail_index:
            for i in range(len(fund_detail_index)):
                fund_detail_data = self.tables[fund_detail_index[i][0]][fund_detail_index[i][1] + 1]
                fund_detail_data.append(self.tables[fund_detail_index[i][0]][fund_detail_index[i][1] + 3][0])
                fund_detail_data.append(self.tables[fund_detail_index[i][0]][fund_detail_index[i][1] + 3][-1])
                fund_detail_data = [item for item in fund_detail_data if item is not None]
                if len(fund_detail_data) >= len(fund_detail_column):
                    fund_detail_data = [fund_detail_data[j:j + len(fund_detail_column)] for j in range(0, len(fund_detail_data), len(fund_detail_column))]
                    all_fund_detail_data.extend(fund_detail_data)
                else:
                    print("Insufficient data to match the columns")
            if all_fund_detail_data:
                fund_detail_df = pd.DataFrame(all_fund_detail_data, columns=fund_detail_column)
                fund_detail_df = fund_detail_df.dropna(axis=1)
            else:
                fund_detail_df = None
        else:
            fund_detail_df = None
        return fund_detail_df

    def extract_subsidy_detail(self):
        subsidy_detail_index = self.get_index(self.tables, '家庭月收入')
        practise_detail_index = self.get_index(self.tables, '执业资格名称')
        if subsidy_detail_index:
            subsidy_detail_column = self.tables[subsidy_detail_index[0][0]][subsidy_detail_index[0][1]]
            if practise_detail_index:
                subsidy_detail_data = self.tables[subsidy_detail_index[0][0]][subsidy_detail_index[0][1] + 1:practise_detail_index[0][1]]
                practise_detail_column = self.tables[practise_detail_index[0][0]][practise_detail_index[0][1]]
                practise_detail_data = self.tables[practise_detail_index[0][0]][practise_detail_index[0][1] + 1:]
            else:
                subsidy_detail_data = self.tables[subsidy_detail_index[0][0]][subsidy_detail_index[0][1] + 1:]
                practise_detail_data = []
            subsidy_detail_data = [item for item in subsidy_detail_data if item is not None]
            subsidy_detail_df = pd.DataFrame(subsidy_detail_data, columns=subsidy_detail_column)
            practise_detail_df = pd.DataFrame(practise_detail_data, columns=practise_detail_column)
            subsidy_detail_df = subsidy_detail_df.dropna(axis=1)
            practise_detail_df = practise_detail_df.dropna(axis=1)
        else:
            subsidy_detail_df = None
            practise_detail_df = None
        return subsidy_detail_df, practise_detail_df

    def extract_identify_detail(self):
        identify_detail_index = self.get_index(self.tables, '认定类别')
        all_identify_detail_data = []
        if identify_detail_index:
            for i in range(len(identify_detail_index)):
                identify_detail_column = self.tables[identify_detail_index[i][0]][identify_detail_index[i][1]]
                identify_detail_data = self.tables[identify_detail_index[i][0]][identify_detail_index[i][1] + 1]
                identify_detail_data = [item for item in identify_detail_data if item is not None]
                if len(identify_detail_data) >= len(identify_detail_column):
                    identify_detail_data = [identify_detail_data[j:j + len(identify_detail_column)] for j in range(0, len(identify_detail_data), len(identify_detail_column))]
                    all_identify_detail_data.extend(identify_detail_data)
                else:
                    print("Insufficient data to match the columns")
            if all_identify_detail_data:
                identify_detail_df = pd.DataFrame(all_identify_detail_data, columns=identify_detail_column)
                identify_detail_df = identify_detail_df.dropna(axis=1)
            else:
                identify_detail_df = None
        else:
            identify_detail_df = None
        return identify_detail_df

    def extract_punish_detail(self):
        punish_detail_index = self.get_index(self.tables, '惩戒类别')
        all_punish_detail_data = []
        if punish_detail_index:
            for i in range(len(punish_detail_index)):
                punish_detail_column = self.tables[punish_detail_index[i][0]][punish_detail_index[i][1]]
                punish_detail_data = self.tables[punish_detail_index[i][0]][punish_detail_index[i][1] + 1]
                punish_detail_data = [item for item in punish_detail_data if item is not None]
                if len(punish_detail_data) >= len(punish_detail_column):
                    punish_detail_data = [punish_detail_data[j:j + len(punish_detail_column)] for j in range(0, len(punish_detail_data), len(punish_detail_column))]
                    all_punish_detail_data.extend(punish_detail_data)
                else:
                    print("Insufficient data to match the columns")
            if all_punish_detail_data:
                punish_detail_df = pd.DataFrame(all_punish_detail_data, columns=punish_detail_column)
                punish_detail_df = punish_detail_df.dropna(axis=1)
            else:
                punish_detail_df = None
        else:
            punish_detail_df = None
        return punish_detail_df

    def extract_query_detail(self):
        query_detail_index = self.get_index(self.tables, '查询日期')
        query_detail_column = ['编号', '查询日期', '查询机构', '查询原因']
        if query_detail_index:
            if len(query_detail_index) > 1:
                query_detail_data = self.tables[query_detail_index[0][0]][query_detail_index[0][1] + 1:query_detail_index[1][1]] + self.tables[query_detail_index[0][0]][query_detail_index[1][1] + 1:]
            else:
                query_detail_data = self.tables[query_detail_index[0][0]][query_detail_index[0][1] + 1:]
            query_detail_data = [item for sublist in query_detail_data for item in sublist]
            query_detail_data = [query_detail_data[j:j + len(query_detail_column)] for j in range(0, len(query_detail_data), len(query_detail_column))]
            query_detail_df = pd.DataFrame(query_detail_data, columns=query_detail_column)
            query_detail_df = query_detail_df.dropna(axis=1)
        else:
            query_detail_df = None
        return query_detail_df
 #报告有效性校验程序


class ReportValidator:
    @staticmethod
    def validate_report(report_info: dict, path: str) -> tuple:
        checks = [
            (ReportValidator.check_reporttime_no, [report_info], "报告时间和报告编号校验不通过"),
            # (ReportValidator.check_reporttime_deadline, [report_info, text], "报告时间和有效期校验不通过"),
            (ReportValidator.check_filemeta, [path], "文档属性信息校验不通过"),
            (ReportValidator.check_font, [path], "文档字体校验不通过"),
        ]
        
        for check_func, args, error_message in checks:
            if not check_func(*args):
                return False, error_message
        
        return True, "报告防篡改验证通过"

    @staticmethod
    def check_reporttime_no(report_info: dict) -> bool:
        
        report_time  = report_info.get('report_date') or report_info.get('报告日期')
        report_no = report_info.get('report_number') or report_info.get('报告编号')
        # print(report_time)
        # print(report_no)
        if not report_time or not report_no:
            return False
        
        report_no_split = report_no[:14]
        report_time_temp = report_time.replace('-', '').replace('T', '').replace(':', '').replace(' ','').replace('.','')
        
        return report_no_split == report_time_temp

    @staticmethod
    def check_reporttime_deadline(report_info: dict, text: str) -> bool:
        report_time_str = report_info.get('report_date', '')[:10]
        report_time = datetime.strptime(report_time_str, "%Y-%m-%d")
        deadline = re.findall(r'有效期：(\d{4}-\d{2})', text)
        
        if not deadline:
            return False
        
        deadline_temp = datetime.strptime(deadline[0], "%Y-%m")
        return (
            (report_time.year == deadline_temp.year and report_time.month in [deadline_temp.month + 1, deadline_temp.month + 2]) or
            (report_time.year == deadline_temp.year + 1 and report_time.month in [1, 2] and deadline_temp.month == 12)
        )

    @staticmethod
    def check_filemeta(path: str) -> bool:
        pdf_reader = PdfReader(path)
        info_dict = pdf_reader.metadata
    
        # Check the producer
        producer_check = info_dict.get('/Producer').replace(" ","") == 'iText2.1.7by1T3XT'
    
        # Retrieve and convert dates
        mod_date = info_dict.get('/ModDate')
        creation_date = info_dict.get('/CreationDate')
        
        if mod_date and creation_date:
            try:
                # Convert the dates to datetime objects
                mod_date = mod_date.replace("D:","").replace("+08'00'","")
                creation_date = creation_date.replace("D:","").replace("+08'00'","")
                mod_date_obj = datetime.strptime(mod_date, "%Y%m%d%H%M%S")  # Adjust format as needed
                creation_date_obj = datetime.strptime(creation_date, "%Y%m%d%H%M%S")  # Adjust format as needed
                
                # Check if year, month, and day are the same
                date_check = (mod_date_obj.year == creation_date_obj.year and
                              mod_date_obj.month == creation_date_obj.month and
                              mod_date_obj.day == creation_date_obj.day)
            except ValueError:
                # Handle the case where date conversion fails
                date_check = False
        else:
            date_check = False  # Handle cases where one or both dates are None
    
        return producer_check and date_check

    @staticmethod
    def check_font(path: str) -> bool:
        with open(path, "rb") as file:
            reader = PdfReader(file)
            fonts = set()
            for page in reader.pages:
                page_resources = page.get('/Resources', {})
                if '/Font' in page_resources:
                    font_resources = page_resources['/Font']
                    for font_name in font_resources.keys():
                        font = font_resources[font_name]
                        fonts.add(font.get('/BaseFont', ''))
        
        return len(fonts) == 2 and '/Helvetica' in fonts and any('SourceHanSerifCN' in font for font in fonts)
def get_data(path):
    extractor = cp.PDFExtractor(path)
    text_1 = extractor.extract_text(1)
    # print(text_1)
    if '企业信用报告' in text_1:
       cleaner = DataCleaner()
       text = extractor.extract_text(5)
       tables = extractor.extract_tables()
       tables = cleaner.clean_data(tables)
       parser = CR_CIParser(path, text, tables)
       report_info = parser.extract_report_info()
       
       com_base = parser.get_com_base_data(report_info)
       
       holder,manager = parser.get_com_person_data(report_info)
       
       summary_data = parser.get_summary_data(report_info)
       
           
       summary_data_2 = parser.flatten_dict(parser.get_summary_data_2(report_info))
       neg_summary_data = parser.get_neg_summary_data(report_info)
       outstanding_bad_summary = parser.flatten_dict(parser.get_outstanding_bad_summary_data(report_info))
       outstanding_acount_data = parser.flatten_dict(parser.get_outstanding_account_data(report_info))
       circle_summary = parser.flatten_dict(parser.get_circle_summary_data(report_info))
       repay_liability_summary = parser.flatten_dict(parser.get_repay_liability_summary_data(report_info))
       repayed_bad_summary = parser.flatten_dict(parser.get_payed_bad_summary_data(report_info))
       payed_summary =parser.flatten_dict(parser.get_payed_summary_data(report_info))
       recovered_detail =parser.get_recovered_detail_data(report_info)
       nopay_loan_detail,nopay_circle_detail = parser.get_nopay_loan_detail_data(report_info)

       nopay_discount_detail =parser.get_nopay_discount_detail_data(report_info)
       bank_letter_detail = parser.get_bank_letter_detail_data(report_info)
       
       # nopay_liabillity_detail = get_liabillity_detail_data(report_info)
       credit_detail = parser.get_credit_detail_data(report_info)
       payed_detail = parser.get_payed_detail_data(report_info)
       payed_discount  = parser.get_payed_discount_data(report_info)
       payed_bankdraft = parser.get_payed_bankdraft_data(report_info)
       liabillity_detail = parser.get_liabillity_detail_data(report_info)
       appendix_loan_detail = parser.get_appendix_loan_detail(report_info)
       appendix_circle_detail = parser.get_appendix_circle_detail(report_info)
       appendix_bankdraft_letter = parser.get_appendix_bankdraft_letter_detail(report_info)
       # print(liabillity_detail)
       public_fee = parser.get_public_fee_data(report_info)


       owed_taxes = parser.get_owed_taxes_data(report_info)
       license_data = parser.get_license_data(report_info)
       certification_data = parser.get_certification_data(report_info)
       qualification_data = parser.get_qualification_data(report_info)
       award_data = parser.get_award_data(report_info)
       approve_data = parser.get_approve_data(report_info)
       no_check = parser.get_no_check_data(report_info)
       patent  = parser.get_patent_data(report_info)


       all_data = [
           com_base, holder, manager, summary_data, summary_data_2, neg_summary_data,
           outstanding_bad_summary, outstanding_acount_data, circle_summary,
           repay_liability_summary, repayed_bad_summary, payed_summary, recovered_detail,
           nopay_loan_detail, nopay_circle_detail, nopay_discount_detail, bank_letter_detail,
           liabillity_detail, credit_detail, payed_detail, payed_discount, payed_bankdraft,
           appendix_loan_detail, appendix_circle_detail, appendix_bankdraft_letter,
           public_fee, owed_taxes, license_data, certification_data, qualification_data,
           award_data, approve_data, no_check, patent]

       
       return all_data,asdict(report_info)
    if '个人信用报告' and '身份信息' in text_1:
       parser = CR_PDParser(path)
       info = parser.extract_report_info()
       id_info = parser.extract_id_info()
       addr_info = parser.extract_addr_info()
       career_info = parser.extract_career_info()
       account_info = parser.extract_account_info()
       recovered_account = parser.extract_recovered_account()
       baddebt_account = parser.extract_baddebt_account()
       overdue_account = parser.extract_overdue_account()
       loan_summary = parser.extract_loan_summary()
       liabillity_account = parser.extract_liabillity_account()
       postpaid_info, public_info = parser.extract_postpaid_info()
       query_summary = parser.extract_query_summary()
       liabillity_detail = parser.extract_liabillity_detail()
       credit_detail = parser.extract_credit_detail()

       postpaid_detail = parser.extract_postpaid_detail()
       tax_detail = parser.extract_tax_detail()
       punishment_detail = parser.extract_punishment_detail()
       fund_detail = parser.extract_fund_detail()
       subsidy_detail, practise_detail = parser.extract_subsidy_detail()
       identify_detail = parser.extract_identify_detail()
       punish_detail = parser.extract_punish_detail()
       query_detail = parser.extract_query_detail()
       all_data = [info,id_info,addr_info,career_info,account_info,recovered_account,baddebt_account,overdue_account,loan_summary,
                   liabillity_account,postpaid_info,query_summary,liabillity_detail,credit_detail,postpaid_detail,tax_detail,
                   punishment_detail,fund_detail,subsidy_detail,identify_detail,punish_detail,query_detail]
       return all_data,info
    if '个人信用报告' and '信贷记录' in text_1:
       parser = CR_PSParser(path)
       # print(parser.text)
       if '信用卡\n' in parser.text:
           if '贷款\n' in parser.text[156:]:
               creditcard_text = parser.extract_between(parser.text[156:], '信用卡\n', '贷款\n')
              
           
           elif '相关还款责任信息\n' in parser.text:
               creditcard_text = parser.extract_between(parser.text, '信用卡\n', '相关还款责任信息\n')
       else:
           creditcard_text=None
       # print(parser.text[156:])
       if '贷款\n' in parser.text[156:]:
           if '相关还款责任信息\n' in parser.text:
               loan_text = parser.extract_between(parser.text[156:], '贷款\n', '相关还款责任信息\n')
               
           
           elif '非信贷交易记录\n' in parser.text:
               print(parser.text[156:])
               loan_text = parser.extract_between(parser.text[156:], '贷款\n', '非信贷交易记录\n')
       else:
            loan_text=None

       if '相关还款责任信息\n' in parser.text:
           if '非信贷交易记录\n' in parser.text:
               liability_text = parser.extract_between(parser.text, '相关还款责任信息', '非信贷交易记录\n')
       else:
           liability_text=None
       query_text = parser.extract_between(parser.text, '查询记录\n', '说 明\n')
       
       if creditcard_text:
           
           card_cleaned_text = parser.clean_text(creditcard_text)
           card_data = parser.extract_card_info(card_cleaned_text)
           card_df = pd.DataFrame(card_data)
           card_df = card_df[card_df['金融机构'].notna()]
           card_df['金融机构']=card_df['金融机构'].map(lambda x:x.split('公司')[0]+'公司')
           card_df['余额'].fillna(0,inplace=True)
           card_df['已用额度'].fillna(0,inplace=True)
           card_df['授信额度'].fillna(0,inplace=True)
           card_df['余额'] = pd.to_numeric(card_df['余额'].astype(str).str.replace(',', ''))
           card_df['已用额度'] = pd.to_numeric(card_df['已用额度'].astype(str).str.replace(',', ''))
           card_df['授信额度'] = pd.to_numeric(card_df['授信额度'].astype(str).str.replace(',', ''))
           card_debt=card_df[card_df['账户状态']!='销户'].groupby('金融机构').agg({'已用额度':'sum'})['已用额度'].sum()+card_df[card_df['账户状态']!='销户'].groupby('金融机构').agg({'余额':'sum'})['余额'].sum().astype(float)
           
           card_df_group = card_df[card_df['账户状态']!='销户'].groupby('金融机构').agg({'授信额度':'sum','已用额度':'sum','余额':'sum','账户状态': summarize_status})
           card_df_group['已用额度']=card_df_group['已用额度']+card_df_group['余额']
           card_df_group =card_df_group.drop(columns=['余额']) 
       else:
           card_df_group=None
           card_debt=0
       if  loan_text:
           
           loan_cleaned_text = parser.clean_text(loan_text)
           
           loan_data = parser.extract_loan_info(loan_cleaned_text)
           loan_df = pd.DataFrame(loan_data)
           loan_df = loan_df[loan_df['借款日期'].notna()]
           
           loan_df['金融机构']=loan_df['金融机构'].map(lambda x:x.split('公司')[0]+'公司')
           loan_df['余额'].fillna(0,inplace=True)
           loan_df['授信额度'].fillna(0,inplace=True)
           loan_df['借款金额'].fillna(0,inplace=True)
           loan_df['余额'] = pd.to_numeric(loan_df['余额'].astype(str).str.replace(',', ''))
           loan_df['借款金额'] = pd.to_numeric(loan_df['借款金额'].astype(str).str.replace(',', ''))
           loan_df['授信额度'] = pd.to_numeric(loan_df['授信额度'].astype(str).str.replace(',', ''))
           loan_debt = loan_df[loan_df['借款状态']!='销户'].groupby('金融机构').agg({'余额':'sum'})['余额'].sum().astype(float)
           
           loan_df_group =  loan_df[loan_df['借款状态']!='结清'].groupby('金融机构').agg({'借款金额':'sum','余额':'sum','借款状态': summarize_status})
           # loan_df_group_temp=loan_df_group_temp.reset_index()
           # loan_df_group_temp=loan_df_group_temp.set_index('bank')
           # loan_df_group = loan_df_group_temp.groupby('bank').agg({'loan_amount':'sum','balance':'sum','loan_status': summarize_status})
       else:
           loan_df_group=None
           loan_debt=0
       if liability_text:
           
           liability_cleaned_text = parser.clean_text(liability_text)
           liability_data = parser.extract_liability_info(liability_cleaned_text)
           liability_df = pd.DataFrame(liability_data)
       else:
           liability_df=None
       if  query_text:
           # print("query_text",query_text)
           query_cleaned_text = parser.clean_text(query_text)
           query_df = parser.extract_query_info(query_cleaned_text)
           # print(query_df['查询日期'])
           query_df['查询日期'] = pd.to_datetime(query_df['查询日期'], format='%Y年%m月%d日', errors='coerce')      
           # 获取当前日期
           current_date = datetime.now()
           
           # 计算总查询次数
           total_queries = query_df.shape[0]
           
           # 计算一个月内查询次数
           one_month_ago = current_date - timedelta(days=30)
           one_month_queries = query_df[query_df['查询日期'] >= one_month_ago].shape[0]
           
           # 计算半年内查询次数
           six_months_ago = current_date - timedelta(days=180)
           six_month_queries = query_df[query_df['查询日期'] >= six_months_ago].shape[0]
           
           # 计算一年内查询次数
           one_year_ago = current_date - timedelta(days=365)
           one_year_queries = query_df[query_df['查询日期'] >= one_year_ago].shape[0]
           query_handle = {'查询总次数':total_queries,
                           '一个月内查询次数':one_month_queries,
                           '半年内查询次数':six_month_queries,
                           '一年内查询次数':one_year_queries}
       else:
           query_handle=None
           
       base_data = parser.extract_base_info(parser.text)
       # print('base_data',base_data)
       if base_data:
           
           base_df = pd.DataFrame(base_data)
       else:
           base_df=None
       debt=float(card_debt)+float(loan_debt)
       debt_dict = {"信用卡负债":card_debt,
               "贷款负债":loan_debt,
               "总负债":debt}

      
   
       all_data=[base_df,debt_dict,query_handle,liability_df,card_df_group,loan_df_group]
       return all_data,base_data
@st.cache_data
def main(path: str):
    start_time = time.time()
    try:
        extractor = cp.PDFExtractor(path)
        text = extractor.extract_text(1)
    except Exception:
        raise Exception('你上传的文件不是原始文件，请检查文件属性')
    if text:
        if '企业信用报告' in text:
            tables_temp = extractor.extract_tables()
            tables = extractor.clean_data(tables_temp)
            parser = CR_CIParser(path, text, tables)
            report_info = parser.extract_report_info()
            report_info = asdict(report_info)
        elif '个人信用报告' and '身份信息' in text:
            parser = CR_PDParser(path)
            report_info = parser.extract_report_info()
        elif '个人信用报告' and '信贷记录' in text:
            parser = CR_PSParser(path)
            report_info = parser.extract_base_info(parser.text)
            report_info=report_info[0]
        else:
            raise Exception('你上传的文件不是PDF文件或者不是征信报告')
    else:
        print('未解析到内容')
    try:    
        rv = ReportValidator()
        is_valid, validation_message=rv.validate_report(report_info, path)
    
        
        if not is_valid:
            print(f"不通过原因: {validation_message}")
            return None,validation_message,None
        else:
            all_data,_=get_data(path)
            duration = int(time.time() - start_time)
            return all_data, report_info,duration
    except Exception:
        all_data,_=get_data(path)
        duration = int(time.time() - start_time)
        return all_data, report_info,duration
def continue_parsing(path):
    start_time = time.time()
    data_list,report_info = get_data(path)
        
    duration = int(time.time() - start_time)
    
    if data_list and report_info and duration:
        log_user_info(action="File Parsed", file_name=path)
        st.session_state['data_list'] = data_list
        st.session_state['report_info'] = report_info
        st.session_state['duration'] = duration
        st.success("解析完成！用时{:.2f}秒".format(duration))
    else:
        st.write('解析失败')
        st.write(f'失败的原因是：{report_info}')


def download_excel(data_list, report_info):
    output = BytesIO()
    ExcelWriter.to_excel(output, data_list, report_info)
    processed_data = output.getvalue()
    
    get_file_name = report_info.get('company_name') or report_info.get('被查询者姓名') 
    file_name = get_file_name + ".xlsx"
    
    st.download_button(
        label="下载解析结果Excel文件", 
        data=processed_data, 
        file_name=file_name, 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# 获取用户信息的函数
@st.cache_data
def get_user_info():
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return hostname, ip_address
    except Exception as e:
        logging.error(f"获取用户信息时出错: {e}")
        return "Unknown", "Unknown"

# 记录用户信息的函数
@st.cache_data
def log_user_info(action, file_name=None):
    hostname, ip_address = get_user_info()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Action: {action}, Hostname: {hostname}, IP: {ip_address}, Time: {current_time}, File: {file_name}")

# 设置页面配置
st.set_page_config(page_title="人行征信报告解析工具", layout="wide")

# 显示标题
st.markdown(
    "<h1 style='text-align: center;'>风控百宝箱—征信报告解析工具V2.0</h1>",
    unsafe_allow_html=True
)



# 创建上传文件夹
upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)

# 初始化会话状态变量
if 'uploaded' not in st.session_state:
    st.session_state['uploaded'] = False
if 'data_list' not in st.session_state:
    st.session_state['data_list'] = None
if 'report_info' not in st.session_state:
    st.session_state['report_info'] = None

# 创建左右两列布局
col1, col2 = st.columns([1, 2])  # 左边占1，右边占2

# 左侧功能区：上传按钮
with st.sidebar:
    image_path = "E:\SynologyDrive\风控工具项目\文件\QR_WECHAT.jpg"
    # image_path = "QR_WECHAT.jpg"
    st.sidebar.image(image_path, caption='作者微信', use_column_width=True)
    st.subheader("提示")
    st.markdown("1. 本工具支持人行企业征信报告自查版、人行个人征信报告自查版简版和详版。")
    st.markdown("2. 本工具只支持官网下载PDF文件，不支持扫扫描件。")
    uploaded_file = st.file_uploader("上传一个PDF文件", type="pdf", label_visibility='visible')
    
    

    if uploaded_file is not None:
        # 获取上传文件名并创建新文件名
        uploaded_file_name = uploaded_file.name
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_file_name = f"{uploaded_file_name.rsplit('.', 1)[0]}_{current_time}.pdf"
        full_file_path = os.path.join(upload_folder, new_file_name)

        # 保存上传的文件
        with open(full_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # 更新会话状态
        st.session_state['uploaded'] = True
        st.session_state['uploaded_file_name'] = new_file_name

        # 记录用户信息
        log_user_info(action="File Uploaded", file_name=uploaded_file.name)

        # 显示进度条
        with st.spinner("解析中，请稍等"):
            progress_bar = st.progress(0)
            for percent_complete in range(100):
                time.sleep(0.01)  # 模拟解析时间延迟
                progress_bar.progress(percent_complete + 1)

            # 调用主函数解析文件
            try:
                data_list, report_info, duration = main(full_file_path)
                if data_list and report_info and duration:
                    log_user_info(action="File Parsed", file_name=new_file_name)
                    st.session_state['data_list'] = data_list
                    st.session_state['report_info'] = report_info
                    st.session_state['duration'] = duration
                    st.success("你上传的征信报告已通过防篡改校验")
                    st.success(f"解析完成！用时{duration:.2f}秒")
                else:
                    st.write('你上传的征信报告未通过防篡改校验')
                    st.write(f'不通过的原因是：{report_info}')
                    if st.button('继续解析'):
                        continue_parsing(full_file_path)
                    if st.button('结束程序'):
                        st.stop()
            except Exception as e:
                st.error("解析过程中出现错误，请检查上传的文件是征信报告，且是未经加工的")
                logging.error(f"Error occurred during parsing: {e}", exc_info=True)
    

    # Main logic to handle report types and download
    if st.session_state['uploaded'] and st.session_state['data_list'] is not None and st.session_state['report_info'] is not None:
        info = st.session_state['report_info']
        
        if 'company_name' in info:
            print('这是企业信用报告')
            download_excel(st.session_state['data_list'], info)

        elif '被查询者姓名' in info:
            print('这是个人信用报告详版')
            download_excel(st.session_state['data_list'], info)

        else:
            print('这是个人信用报告简版')
            
            if isinstance(info, dict):
                file_name = info.get('姓名')
            elif isinstance(info, list):
                file_name = info[0].get('姓名')
            elif isinstance(info, pd.DataFrame):
                file_name = info['姓名']
            save_file_name = os.path.join(upload_folder, file_name + ".xlsx")
            custom_excel_writer = ot.CustomExcelWriter(save_file_name)

            # Add sheets to the Excel file
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][0], title="基础信息", start_col=2, header=True, borders="medium")
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][1], title="负债信息", start_col=2, header=True, borders="medium")
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][2], title="查询信息", start_col=2, header=True, borders="medium")
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][4], title="信用卡信息", start_col=2, index=True, header=True, borders="medium")
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][5], title="借款信息", start_col=2, index=True, header=True, borders="medium")
            custom_excel_writer.add_sheet('个人人行征信解析结果', st.session_state['data_list'][3], title="担保信息", start_col=2, header=True, borders="medium")

            # Save the Excel file
            custom_excel_writer.save()

            # Read the saved file into memory for download
            with open(save_file_name, "rb") as f:
                processed_data = f.read()

            # Provide download button for the Excel file
            st.download_button(
                label="下载解析结果Excel文件", 
                data=processed_data, 
                file_name=f"{file_name}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# 右侧功能区：显示解析结果

if st.session_state['uploaded']:
    st.subheader("解析结果")
    
    # # 显示 report_info
    # if st.session_state['report_info'] is not None:
    #     st.write("报告信息:")
    #     st.dataframe(st.session_state['report_info'])  # 以JSON格式显示报告信息

    # 显示 data_list
    if st.session_state['data_list'] is not None:
        
        
        # Get titles based on report_info
        data_titles, _ = get_titles(st.session_state['report_info'])
        
        for index, item in enumerate(st.session_state['data_list']):
            st.write(f"### {data_titles[index]}")  # Use titles from get_titles
            
            if isinstance(item, dict) and isinstance(list(item.values())[0], (str, list, int, float, type(None))):
                item = pd.DataFrame([item])
                st.dataframe(item)
            elif isinstance(item, dict) and isinstance(list(item.values())[0],pd.DataFrame):
                for i,v in item.items():
                   st.write(f"#### {i}")
                   st.dataframe(v)
            elif isinstance(item, dict) and isinstance(list(item.values())[0],dict):
                for k,v in item.items():
                    st.write(f"#### {k}")
                    if isinstance(v, dict) and isinstance(list(v.values())[0],dict):
                        for a,b in v.items():
                            st.write(f"#### {a}")
                            item = pd.DataFrame([b])
                            st.dataframe(item)
                    else:
                        item = pd.DataFrame([v])
                        st.dataframe(item)
                # st.json(item)  # 以JSON格式显示字典
            elif isinstance(item, pd.DataFrame):
                st.dataframe(item)  # 显示DataFrame
            elif isinstance(item, list):
                item = pd.DataFrame(item)
                st.dataframe(item)
            else:
                st.write(item)  # 处理其他类型  # 处理其他类型

        # 筛选功能
        filter_key = st.selectbox("选择要筛选的字段", options=list(st.session_state['data_list'][0].keys()) if isinstance(st.session_state['data_list'][0], dict) else [])
        if filter_key:
            filtered_data = [item[filter_key] for item in st.session_state['data_list'] if isinstance(item, dict) and filter_key in item]
            st.write(f"筛选结果: {filtered_data}")

# 启动成功日志
logging.info('程序启动成功')

# if __name__ == "__main__":
#     # path = r"E:\SynologyDrive\风控工具项目\文件\9.中顺企业信用报告2024081328113434_20240924_020138.pdf"
#     path =r"E:\SynologyDrive\风控工具项目\文件\基叶征信_20240904_084432.pdf"
#     # path=r"E:\SynologyDrive\风控工具项目\文件\黄树森征信.pdf"
#     # path=r"E:\SynologyDrive\风控工具项目\文件\叶权锋征信.pdf"
#     # path=r"E:\SynologyDrive\风控工具项目\文件\陈_20240906_094820.pdf"
#     main(path)