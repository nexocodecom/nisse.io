import unittest
from pathlib import Path
from datetime import datetime
from nisse.models import TimeEntry, User
from nisse.services.xlsx_document_service import XlsxDocumentService
import os


class XlsxDocumentServiceTests(unittest.TestCase):
    @unittest.skip("this test generates temp file")
    def test_save_report(self):
        # arrange
        entires = (
            TimeEntry(duration=5, comment="test 23", report_date=datetime(2018, 1, 2), user=User(first_name="joe")),
            TimeEntry(duration=5, comment="test 55", report_date=datetime(2018, 1, 5), user=User(first_name="mike")))
        # act
        file_path_name = "testDocument.xlsx"
        XlsxDocumentService.save_report(file_path_name, "2018-01-01", "2018-02-01", entires, "nisse tests")
        # assert
        my_file = Path(file_path_name)
        self.assertTrue(my_file.is_file(), " report should be generated")
        # os.remove(file_path_name)  # comment out if you want to check the file
