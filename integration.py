"""Import this helper in the existing calculation route."""
from phase2.database import save_project


def save_calculation(data, qualification, scoring, confidence, extraction=None, source_file=None):
    extraction = extraction or {}
    return save_project(
        data=data,
        qualification=qualification,
        scoring=scoring,
        confidence=confidence,
        source={
            'file_name': source_file,
            'source_type': extraction.get('source_type'),
            'template_version': extraction.get('template_version'),
        },
        warnings=extraction.get('warnings', []),
        extraction=extraction,
    )
