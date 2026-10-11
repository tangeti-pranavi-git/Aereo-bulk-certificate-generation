from django.urls import path
from certificates.views import (
    JobCreateListView,
    JobUploadCSVView,
    JobUploadSpreadsheetView,
    JobDetailView,
    CertificateDownloadView,
    JobDownloadAllZipView,
    CertificateVerifyView,
)

urlpatterns = [
    path('jobs/', JobCreateListView.as_view(), name='job-list-create'),
    path('jobs/upload-file/', JobUploadSpreadsheetView.as_view(), name='job-upload-file'),
    path('jobs/upload-xlsx/', JobUploadSpreadsheetView.as_view(), name='job-upload-xlsx'),
    path('jobs/upload-csv/', JobUploadCSVView.as_view(), name='job-upload-csv'),
    path('jobs/<uuid:job_id>/', JobDetailView.as_view(), name='job-detail'),
    path('jobs/<uuid:job_id>/download-all/', JobDownloadAllZipView.as_view(), name='job-download-all-zip'),
    path('certificates/<uuid:certificate_id>/download/', CertificateDownloadView.as_view(), name='certificate-download'),
    path('verify/<str:certificate_code>/', CertificateVerifyView.as_view(), name='certificate-verify'),
]
