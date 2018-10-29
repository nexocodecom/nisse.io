from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl.styles import Font, Color, Border, Side, Alignment, colors
from itertools import groupby
from nisse.utils.date_helper import *
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

        # project selected, group by users
        if project:
            self.genereate_per_user_summarized(wb, date_from, date_to, time_entries)

        # user selected, group by projects
        else:
            self.genereate_per_project_report(wb, date_from, date_to, time_entries, project)

        wb.save(file_path)

    def genereate_per_project_report(self, wb: Workbook, date_from, date_to, time_entries, project):

        time_entries = sorted(time_entries, key=lambda te: te.project.name)
        by_project = groupby(time_entries, key=lambda te: te.project.name)

        project_name = project.name if project is not None else "All projects"

        sheet = wb.active
        sheet.title = "Time Entries Report"

        sheet.column_dimensions['A'].width = 20
        sheet.column_dimensions['B'].width = 15
        sheet.column_dimensions['C'].width = 15
        sheet.column_dimensions['D'].width = 15
        sheet.column_dimensions['E'].width = 50

        self.put_text(sheet['A1'], "Time report for project:")
        self.put_text(sheet['B1'], project_name, font=self.font_red_bold)
        self.put_text(sheet['A2'], "Date from:")
        self.put_text(sheet['B3'], date_from)
        self.put_text(sheet['A2'], "Date to:")
        self.put_text(sheet['B3'], date_to)

        self.put_text(sheet['A5'], "Project", font=self.font_bold)
        self.put_text(sheet['B5'], "Date Time", font=self.font_bold)
        self.put_text(sheet['C5'], "Duration", font=self.font_bold)
        self.put_text(sheet['D5'], "Employee", font=self.font_bold)
        self.put_text(sheet['E5'], "Comment", font=self.font_bold)

        i = 5
        for project_name, group in by_project:
            i_start = i + 1
            self.put_text(sheet['A' + str(i+1)], project_name)
            group_sorted = sorted(group, key=lambda te: te.report_date)
            for t in group_sorted:
                i += 1
                self.put_text(sheet['B' + str(i)], t.report_date.strftime('%Y-%m-%d'))
                self.put_time(sheet['C' + str(i)], t.duration)
                self.put_text(sheet['D' + str(i)], str(t.user.first_name))
                self.put_text(sheet['E' + str(i)], t.comment)
            i += 1
            self.put_text(sheet['B' + str(i)], "Sum:", font=self.font_bold)
            self.put_time(sheet['C' + str(i)], "=SUM($C$" + str(i_start) + ":$C$" + str(i - 1) + ")", font=self.font_bold)

        i += 1
        self.put_text(sheet['B' + str(i)], 'Total:', font=self.font_bold, border=self.top_border)
        self.put_time(sheet['C' + str(i)], sum(te.duration for te in time_entries), font=self.font_bold, border=self.top_border)

    def genereate_per_user_summarized(self, wb: Workbook, date_from, date_to, time_entries):

        time_entries = sorted(time_entries, key=lambda te: te.user.first_name)
        by_user = groupby(time_entries, key=lambda te: te.user.first_name)

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

            sheet.column_dimensions['A'].width = 18
            sheet.column_dimensions['B'].width = 10
            sheet.column_dimensions['C'].width = 60

            self.put_text(sheet['A1'], "Date", font=self.font_bold)
            self.put_text(sheet['B1'], "Duration", font=self.font_bold)
            self.put_text(sheet['C1'], "Comment", font=self.font_bold)

            i = 1
            i_start = i + 1
            total_overtime_deficit = 0
            total_basic_deficit = 0
            for date in date_range(datetime.strptime(date_from, "%Y-%m-%d").date(),
                                   datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=1)):
                i += 1
                self.put_text(sheet['A' + str(i)], date.strftime("%Y-%m-%d"), font=(self.font_red if is_weekend(date) else None))

                tes = list(filter(lambda te: te.report_date == date, group_sorted))
                time_reported = sum(te.duration for te in tes)
                comment = ""
                for te in tes:
                    comment += te.comment

                self.put_time(sheet['B' + str(i)], time_reported)
                self.put_text(sheet['C' + str(i)], comment.replace("\n\n", "\n"))

                basic = 0
                deficit = 0
                if not is_weekend(date):
                    basic = time_reported if time_reported <= 8 else 8
                    deficit = 8 - basic if time_reported <= 8 else 0
                total_overtime_deficit += (time_reported - basic - deficit)
                total_basic_deficit += (basic + deficit)

            i += 1
            self.put_time(sheet['B' + str(i)], str("=SUM(B" + str(i_start) + ":B" + str(i-1) + ")"), font=self.font_bold)
            self.put_text(sheet['A' + str(i + 2)], "Overtime:", font=self.font_bold, alignment=self.alignment_right)
            self.put_time(sheet['B' + str(i + 2)], total_overtime_deficit, self.font_bold)
            self.put_text(sheet['A' + str(i + 3)], "Basic hours:", font=self.font_bold, alignment=self.alignment_right)
            self.put_time(sheet['B' + str(i + 3)], total_basic_deficit, self.font_bold)

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
