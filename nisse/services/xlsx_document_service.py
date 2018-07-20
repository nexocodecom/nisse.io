from openpyxl import Workbook
from openpyxl.styles import Font, Color
from openpyxl.styles import colors


class XlsxDocumentService(object):
    """
    This class will save time entries data into xlsx file
    """

    @staticmethod
    def save_report(file_path, date_from, date_to, time_entries, project_name):
        """
        Creates report and saves it into xlsx file
        :param file_path: file destination
        :param date_from: start date for report
        :param date_to: end date for report
        :param time_entries: collection time entries
        :param project_name: project for which report is generated
        :return:
        """
        wb = Workbook()

        sheet = wb.active
        sheet.title = project_name

        sheet.column_dimensions['A'].width = 20
        sheet.column_dimensions['B'].width = 15
        sheet.column_dimensions['C'].width = 15
        sheet.column_dimensions['D'].width = 50

        sheet['A1'] = "Time report for project:"
        sheet['B1'] = project_name
        ft = Font(color=colors.RED, bold=True)
        sheet['B1'].font = ft
        sheet['A2'] = "Date from:"
        sheet['A3'] = "Date to:"

        sheet['B2'] = date_from
        sheet['B3'] = date_to

        sheet['A5'] = "Date Time"
        sheet['B5'] = "Duration"
        sheet['C5'] = "Employee"
        sheet['D5'] = "Comment"

        i = 5
        for n in time_entries:
            i = i + 1
            sheet['A' + str(i)] = n.report_date.strftime('%Y-%m-%d')
            sheet['B' + str(i)] = n.duration
            sheet['C' + str(i)] = str(n.user.first_name) + ' ' + str(n.user.last_name)
            sheet['D' + str(i)] = n.comment

        if i > 5:
            sheet['A' + str(i + 1)] = 'Sum:'
            sheet['B' + str(i + 1)] = "=SUM($B$6:$B$" + str(i) + ")"

            ft = Font(bold=True)
            sheet['A' + str(i + 1)].font = ft
            sheet['B' + str(i + 1)].font = ft

        wb.save(file_path)
