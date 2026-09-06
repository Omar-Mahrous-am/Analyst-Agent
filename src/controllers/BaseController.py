"""
Base controller for the SmartDesk AI application.

This module provides common configuration and utilities that are shared
across all controllers in the application, such as environment variable
loading and default directory paths.
"""
import os


class BaseController:
    """
    A foundational controller class intended to be inherited by other controllers.

    This class encapsulates common initialization logic, such as loading API keys
    and setting up base directories for file operations, ensuring consistency
    and reducing code duplication across derived controllers.

    Attributes:
        OpenAI_API_KEY (str): The API key for OpenAI, loaded from the environment.
        files_dir (str): The base directory path used for storing assets like documents.
    """

    def __init__(self):
        """
        Initializes the BaseController.

        Loads necessary environment variables and configures standard paths
        used by the application's file handling systems.
        """
        self.OpenAI_API_KEY = os.getenv("OPENAI_API_KEY")


        self.database_dir=os.path.join("src", "assets/database")



    def get_database_path(self,db_name):
        database_path=os.path.join(self.database_dir,db_name)
        if not os.path.exists(database_path):
            os.makedirs(database_path)
        return database_path


