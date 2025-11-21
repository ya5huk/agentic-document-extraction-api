"""
S3 Service Module

Handles all AWS S3 operations including file uploads, bucket validation,
and error handling for the document extraction API.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service class for managing AWS S3 operations.

    Handles file uploads to S3 with proper error handling, validation,
    and logging.
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        """
        Initialize S3 service with AWS credentials.

        Args:
            aws_access_key_id: AWS access key (defaults to env variable)
            aws_secret_access_key: AWS secret key (defaults to env variable)
            region_name: AWS region (defaults to us-east-1)

        Raises:
            ValueError: If credentials are missing
        """
        # Get credentials from parameters or environment variables
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region_name = region_name or "us-east-1"

        # Validate credentials
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise ValueError(
                "AWS credentials are required. Please set AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY environment variables or pass them to constructor."
            )

        # Initialize boto3 S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            logger.info(f"S3 service initialized with region: {self.region_name}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise

    def validate_bucket_access(self, bucket: str) -> bool:
        """
        Check if bucket exists and we have write permissions.

        Args:
            bucket: S3 bucket name

        Returns:
            True if bucket is accessible, False otherwise
        """
        try:
            # Try to get bucket location (requires read access)
            self.s3_client.head_bucket(Bucket=bucket)
            logger.info(f"Bucket '{bucket}' is accessible")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                logger.error(f"Bucket '{bucket}' does not exist")
            elif error_code == '403':
                logger.error(f"Access denied to bucket '{bucket}'")
            else:
                logger.error(f"Error accessing bucket '{bucket}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating bucket '{bucket}': {e}")
            return False

    def upload_file(
        self,
        file_path: str,
        bucket: str,
        s3_key: str,
        validate_bucket: bool = True
    ) -> str:
        """
        Upload a file to S3 and return the S3 URI.

        Args:
            file_path: Local path to the file to upload
            bucket: S3 bucket name
            s3_key: S3 object key (path within bucket)
            validate_bucket: Whether to validate bucket access first

        Returns:
            S3 URI in format: s3://bucket/key

        Raises:
            FileNotFoundError: If local file doesn't exist
            ValueError: If bucket is invalid
            Exception: For S3 upload failures
        """
        # Validate local file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Local file not found: {file_path}")

        if not file_path_obj.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Validate bucket access if requested
        if validate_bucket and not self.validate_bucket_access(bucket):
            raise ValueError(f"Cannot access bucket: {bucket}")

        # Upload file to S3
        try:
            logger.info(f"Uploading '{file_path_obj.name}' to s3://{bucket}/{s3_key}")

            self.s3_client.upload_file(
                Filename=str(file_path_obj),
                Bucket=bucket,
                Key=s3_key
            )

            s3_uri = f"s3://{bucket}/{s3_key}"
            logger.info(f"Successfully uploaded to: {s3_uri}")

            return s3_uri

        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise Exception("AWS credentials not found. Please configure credentials.")

        except PartialCredentialsError:
            logger.error("Incomplete AWS credentials")
            raise Exception("Incomplete AWS credentials. Please provide both access key and secret key.")

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 upload failed with error {error_code}: {error_message}")
            raise Exception(f"S3 upload failed: {error_message}")

        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            raise Exception(f"Failed to upload file to S3: {str(e)}")

    def upload_multiple_files(
        self,
        file_paths: list[str],
        bucket: str,
        s3_prefix: str = ""
    ) -> list[str]:
        """
        Upload multiple files to S3 with the same prefix.

        Args:
            file_paths: List of local file paths to upload
            bucket: S3 bucket name
            s3_prefix: Common prefix for all S3 keys (e.g., "folder/subfolder/")

        Returns:
            List of S3 URIs for successfully uploaded files

        Raises:
            Exception: If all uploads fail
        """
        # Validate bucket once for all uploads
        if not self.validate_bucket_access(bucket):
            raise ValueError(f"Cannot access bucket: {bucket}")

        # Ensure prefix ends with / if provided
        if s3_prefix and not s3_prefix.endswith('/'):
            s3_prefix = s3_prefix + '/'

        uploaded_uris = []
        failed_uploads = []

        for file_path in file_paths:
            try:
                # Get filename and create S3 key
                filename = Path(file_path).name
                s3_key = f"{s3_prefix}{filename}"

                # Upload file (skip bucket validation since we already did it)
                s3_uri = self.upload_file(
                    file_path=file_path,
                    bucket=bucket,
                    s3_key=s3_key,
                    validate_bucket=False
                )

                uploaded_uris.append(s3_uri)

            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")
                failed_uploads.append((file_path, str(e)))

        # Log summary
        logger.info(f"Upload summary: {len(uploaded_uris)} succeeded, {len(failed_uploads)} failed")

        if failed_uploads:
            logger.warning("Failed uploads:")
            for file_path, error in failed_uploads:
                logger.warning(f"  - {file_path}: {error}")

        # If all uploads failed, raise exception
        if not uploaded_uris:
            raise Exception("All file uploads failed. Check logs for details.")

        return uploaded_uris

    def delete_file(self, bucket: str, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            bucket: S3 bucket name
            s3_key: S3 object key to delete

        Returns:
            True if deletion was successful
        """
        try:
            logger.info(f"Deleting s3://{bucket}/{s3_key}")
            self.s3_client.delete_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Successfully deleted s3://{bucket}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete s3://{bucket}/{s3_key}: {e}")
            return False
