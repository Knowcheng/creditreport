from datetime import datetime
from PyPDF2 import PdfReader


class ReportValidator:
    @staticmethod
    def validate_report(report_info: dict, file_path: str) -> tuple[bool, str]:
        checks = [
            (ReportValidator.check_reporttime_no, [report_info], "报告时间和报告编号校验不通过"),
            (ReportValidator.check_filemeta, [file_path], "文档属性信息校验不通过"),
            (ReportValidator.check_font, [file_path], "文档字体校验不通过"),
        ]
        for check_func, args, error_message in checks:
            if not check_func(*args):
                return False, error_message
        return True, "报告防篡改验证通过"

    @staticmethod
    def check_reporttime_no(report_info: dict) -> bool:
        report_time = report_info.get("report_date") or report_info.get("报告日期")
        report_no = report_info.get("report_number") or report_info.get("报告编号")
        if not report_time or not report_no:
            return False
        report_no_split = report_no[:14]
        report_time_temp = (
            report_time.replace("-", "").replace("T", "")
            .replace(":", "").replace(" ", "").replace(".", "")
        )
        return report_no_split == report_time_temp

    @staticmethod
    def check_filemeta(path: str) -> bool:
        try:
            pdf_reader = PdfReader(path)
            info_dict = pdf_reader.metadata
            producer_check = info_dict.get("/Producer", "").replace(" ", "") == "iText2.1.7by1T3XT"
            mod_date = info_dict.get("/ModDate", "")
            creation_date = info_dict.get("/CreationDate", "")
            if mod_date and creation_date:
                mod_date = mod_date.replace("D:", "").replace("+08'00'", "")
                creation_date = creation_date.replace("D:", "").replace("+08'00'", "")
                mod_dt = datetime.strptime(mod_date, "%Y%m%d%H%M%S")
                create_dt = datetime.strptime(creation_date, "%Y%m%d%H%M%S")
                date_check = (mod_dt.year == create_dt.year and
                              mod_dt.month == create_dt.month and
                              mod_dt.day == create_dt.day)
            else:
                date_check = False
            return producer_check and date_check
        except Exception:
            return False

    @staticmethod
    def check_font(path: str) -> bool:
        try:
            with open(path, "rb") as file:
                reader = PdfReader(file)
                fonts = set()
                for page in reader.pages:
                    resources = page.get("/Resources", {})
                    if "/Font" in resources:
                        for font_name in resources["/Font"].keys():
                            font = resources["/Font"][font_name]
                            fonts.add(font.get("/BaseFont", ""))
            return len(fonts) == 2 and "/Helvetica" in fonts and any(
                "SourceHanSerifCN" in f for f in fonts
            )
        except Exception:
            return False
