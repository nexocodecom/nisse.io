from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl.styles import Font, Color, Border, Side, Alignment, colors
from itertools import groupby
from nisse.utils.date_helper import *
from nisse.utils.string_helper import *
from datetime import datetime, timedelta


class XlsxDocumentService(object):
    """
    This class will save time entries data into xlsx file
    """

    font_red = Font(color=colors.RED)
    font_red_bold = Font(color=colors.RED, bold=True)
    font_bold = Font(bold=True)
    top_border = Border(top=Side(style='thin'))
    alignment_right = Alignment(horizontal='right')
    alignment_top = Alignment(vertical='top')

    def save_report(self, file_path, date_from, date_to, time_entries, project):
        """
        Creates report and saves it into xlsx file
        :param file_path: file destination
        :param date_from: start date for report
        :param date_to: end date for report
        :param time_entries: collection time entries
        :param project: project for which report is generated
        :return:
        """

        wb = Workbook()

        time_entries = sorted(time_entries, key=lambda te: get_user_name(te.user))
        by_user = groupby(time_entries, key=lambda te: get_user_name(te.user))

        first_sheet = True
        for first_name, group in by_user:

            group_sorted = list(group)

            sheet = None
            if first_sheet:
                sheet = wb.active
                sheet.title = first_name
                first_sheet = False
            else:
                sheet = wb.create_sheet(first_name)

            sheet.column_dimensions['A'].width = 12
            sheet.column_dimensions['B'].width = 10
            sheet.column_dimensions['C'].width = 20
            sheet.column_dimensions['D'].width = 60

            self.put_text(sheet['A1'], "Date", font=self.font_bold)
            self.put_text(sheet['B1'], "Duration", font=self.font_bold)
            self.put_text(sheet['C1'], "Project", font=self.font_bold)
            self.put_text(sheet['D1'], "Comment", font=self.font_bold)

            i = 1
            i_start = i + 1
            total_basic = 0
            total_deficit = 0
            total_overtime = 0
            for date in date_range(datetime.strptime(date_from, "%Y-%m-%d").date(),
                                   datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=1)):

                tes = list(filter(lambda te: te.report_date == date, group_sorted))
                time_reported = sum(te.duration for te in tes)

                self.put_text(sheet['A' + str(i + 1)], format_date(date),
                              font=(self.font_red if is_weekend(date) else None), alignment=self.alignment_top)

                for te in tes:
                    i += 1
                    self.put_time(sheet['B' + str(i)], te.duration)
                    self.put_time(sheet['C' + str(i)], te.project.name)
                    self.put_text(sheet['D' + str(i)], te.comment)

                if not len(tes):
                    i += 1
                    self.put_time(sheet['B' + str(i)], 0)

                to_merge = len(tes) - 1 if len(tes) else 0
                sheet.merge_cells("A" + str(i - to_merge) + ":A" + str(i))

                basic = 0
                deficit = 0
                if not is_weekend(date) and time_reported:
                    basic = time_reported if time_reported <= 8 else 8
                    deficit = 8 - basic if time_reported <= 8 else 0
                overtime = time_reported - basic
                total_overtime += overtime
                total_deficit += deficit
                total_basic += basic

            total_overtime_deficit = total_overtime - total_deficit if (total_overtime - total_deficit) > 0 else 0
            total_basic_deficit = total_basic + total_deficit if total_overtime_deficit > 0 else total_basic + total_overtime

            i += 1
            self.put_time(sheet['B' + str(i)], str("=SUM(B" + str(i_start) + ":B" + str(i - 1) + ")"),
                          font=self.font_bold)
            self.put_text(sheet['A' + str(i + 2)], "Overtime:", font=self.font_bold, alignment=self.alignment_right)
            self.put_time(sheet['B' + str(i + 2)], total_overtime_deficit, self.font_bold)
            self.put_text(sheet['A' + str(i + 3)], "Basic hours:", font=self.font_bold, alignment=self.alignment_right)
            self.put_time(sheet['B' + str(i + 3)], total_basic_deficit, self.font_bold)

        wb.save(file_path)

    def put_time(self, cell: Cell, duration, font=None, border=None, alignment=None):
        cell = self.put_text(cell, duration, font, border, alignment)
        cell.number_format = '0.00'
        return cell

    def put_text(self, cell: Cell, text, font=None, border=None, alignment=None):
        cell.value = text
        if font:
            cell.font = font
        if border:
            cell.border = border
        if alignment:
            cell.alignment = alignment
        return cell
