import os
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MTurkService:
    """
    A service class to encapsulate all interactions with the Amazon Mechanical Turk (mTurk) API.
    """
    def __init__(self):
        """
        Initializes the MTurk client based on environment variables.
        """
        self.region_name = os.getenv('MTURK_REGION_NAME', 'us-east-1')
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.environment = os.getenv('MTURK_ENVIRONMENT', 'sandbox')

        # Determine the correct endpoint URL for sandbox or production
        endpoint_url = 'https://mturk-requester-sandbox.us-east-1.amazonaws.com'
        if self.environment == 'production':
            endpoint_url = 'https://mturk-requester.us-east-1.amazonaws.com'

        # Check for credentials
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            logger.warning("AWS credentials not found in environment variables. MTurkService will not be available.")
            self.client = None
        else:
            try:
                self.client = boto3.client(
                    'mturk',
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    endpoint_url=endpoint_url
                )
                logger.info(f"MTurkService initialized for '{self.environment}' environment.")
            except Exception as e:
                logger.error(f"Failed to initialize MTurk client: {e}")
                self.client = None

    def get_account_balance(self):
        """
        Retrieves the available balance in the mTurk account.
        Returns the balance as a string, or None if an error occurs.
        """
        if not self.client:
            logger.error("MTurk client not initialized.")
            return None
        try:
            response = self.client.get_account_balance()
            return response['AvailableBalance']
        except ClientError as e:
            logger.error(f"Could not get account balance: {e}")
            return None

    def list_assignments_for_hit(self, hit_id):
        """
        Retrieves all assignments for a given HIT.
        Handles pagination to get all results.
        """
        if not self.client:
            logger.error("MTurk client not initialized.")
            return []
        
        assignments = []
        try:
            paginator = self.client.get_paginator('list_assignments_for_hit')
            page_iterator = paginator.paginate(HITId=hit_id)
            for page in page_iterator:
                assignments.extend(page['Assignments'])
        except ClientError as e:
            logger.error(f"Could not list assignments for HIT {hit_id}: {e}")
            return []
        
        return assignments

    def approve_assignment(self, assignment_id, feedback=''):
        """
        Approves a specified assignment.
        """
        if not self.client:
            logger.error("MTurk client not initialized.")
            return False
        try:
            self.client.approve_assignment(
                AssignmentId=assignment_id,
                RequesterFeedback=feedback,
                OverrideRejection=False  # Set to True if you want to approve a previously rejected assignment
            )
            logger.info(f"Successfully approved assignment {assignment_id}")
            return True
        except ClientError as e:
            logger.error(f"Could not approve assignment {assignment_id}: {e}")
            return False

    def reject_assignment(self, assignment_id, reason=''):
        """
        Rejects a specified assignment.
        """
        if not self.client:
            logger.error("MTurk client not initialized.")
            return False
        try:
            self.client.reject_assignment(
                AssignmentId=assignment_id,
                RequesterFeedback=reason
            )
            logger.info(f"Successfully rejected assignment {assignment_id}")
            return True
        except ClientError as e:
            logger.error(f"Could not reject assignment {assignment_id}: {e}")
            return False

# Create a singleton instance of the service for the application to use
mturk_service = MTurkService()
