from sqlalchemy import select, delete, update, create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional

class Base(DeclarativeBase):
    pass

class CaseRecord(Base):
    __tablename__ = "case_videos"

    media_uuid: Mapped[str] = mapped_column(primary_key=True, index=True)
    upload_datetime: Mapped[str] = mapped_column(index=True)
    file_name: Mapped[str] = mapped_column(index=True)
    file_path: Mapped[str] = mapped_column(index=True)
    source_url: Mapped[Optional[str]] = mapped_column(index= True)
    media_type: Mapped[str] = mapped_column(index=True)
    deepfake: Mapped[Optional[bool]] = mapped_column(index=True)
    summary: Mapped[Optional[str]] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(index=True)

    def __repr__(self) -> str:
        """Returns a string representation of the CaseRecord object.

        Returns:
            str: A string representation of the object.
        """
        return f"CaseRecord(media_uuid={self.media_uuid!r},\
                upload_datetime:{self.upload_datetime!r},\
                file_name={self.file_name!r},\
                file_path={self.file_path!r},\
                source_url={self.source_url!r},\
                media_type={self.media_type!r},\
                deepfake={self.deepfake!r},\
                summary={self.summary!r},\
                status={self.status!r})"

class DatabaseOperations:
    DATABASE_URL = 'sqlite:///storage/case_videos.db'
    database_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database_engine)

    @classmethod
    def initialise_db(cls):
        """Initialises the database by creating all tables defined in Base.metadata.
        """
        Base.metadata.create_all(cls.database_engine)

    @classmethod
    async def get_db(cls):
        """Provides a database session for use in a context manager.

        Yields:
            Session: The database session.
        """
        db = cls.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def create_record(db, media_uuid, upload_datetime, file_name,deepfake, file_path, source_url, media_type, status):
        """Creates a new CaseRecord in the database.

        Args:
            db (Session): The database session.
            media_uuid (str): The UUID of the media.
            upload_datetime (str): The upload datetime string.
            file_name (str): The name of the file.
            deepfake (Optional[bool]): Boolean indicating if the media is a deepfake.
            file_path (str): The path to the media file.
            source_url (Optional[str]): The source URL of the media.
            media_type (str): The type of media (e.g., "video", "image").
            status (str): The status of the record (e.g., "Uploaded", "Completed").
        """
        case_video = CaseRecord(
                                    media_uuid=media_uuid,
                                    upload_datetime=upload_datetime,
                                    file_name=file_name,
                                    deepfake=deepfake,
                                    file_path=file_path,
                                    source_url=source_url,
                                    media_type=media_type,
                                    status=status
                                    )
        db.add(case_video)
        db.commit()
        db.refresh(case_video)


    @staticmethod
    def retrieve_filerecord(db, media_uuid):
        """Retrieves a CaseRecord from the database by its media_uuid.

        Args:
            db (Session): The database session.
            media_uuid (str): The UUID of the media to retrieve.

        Raises:
            HTTPException: If no record is found with the given media_uuid.

        Returns:
            CaseRecord: The retrieved CaseRecord object.
        """
        file_record = db.execute(select(CaseRecord).where(CaseRecord.media_uuid == media_uuid)).scalar_one_or_none()
        if file_record is None:
            raise HTTPException(status_code=404, detail=f"File with UUID {media_uuid} not found")
        return file_record


    @staticmethod
    def update_filerecord(db, media_uuid, summary, deepfake, status):
        """Updates an existing CaseRecord in the database.

        Args:
            db (Session): The database session.
            media_uuid (str): The UUID of the media record to update.
            summary (Optional[str]): The summary text for the media.
            deepfake (Optional[bool]): Boolean indicating if the media is a deepfake.
            status (str): The new status of the record.
        """
        stmt = (
            update(CaseRecord)
            .where(CaseRecord.media_uuid == media_uuid)
            .values(
                summary=summary,
                deepfake=deepfake,
                status=status
            )
        )
        db.execute(stmt)
        db.commit()


    @staticmethod
    def delete_filerecord(db, media_uuid):
        """Deletes a CaseRecord from the database by its media_uuid.

        Args:
            db (Session): The database session.
            media_uuid (str): The UUID of the media record to delete.
        """
        db.execute(delete(CaseRecord).where(CaseRecord.media_uuid == media_uuid))
        db.commit()