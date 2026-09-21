"""Cloud Run entry point using workload identity and PORT."""

import uvicorn
from google.cloud import firestore, storage

from .app import create_app
from .config import from_environment
from .identity import access_identity
from .service import ReportService
from .storage import BucketObjects, FirestoreReports


def main() -> None:
    config = from_environment()
    service = ReportService(
        FirestoreReports(
            firestore.Client(project=config.project_id, database=config.database)
        ),
        BucketObjects(storage.Client(project=config.project_id), config.bucket),
        config.owner_emails,
    )
    app = create_app(
        service,
        access_identity(config.access_issuer, config.access_audience),
        config.public_origin,
    )
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
