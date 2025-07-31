import json
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class JSONStorageService:
    def __init__(self, storage_dir: str = "document_analyses"):
        """Initialize JSON storage service with storage directory"""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save_document_analysis(
        self, session_id: str, analysis_data: Dict[str, Any]
    ) -> str:
        """Save document analysis to JSON file"""
        try:
            # Add metadata
            analysis_data["metadata"] = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "file_version": "1.0",
            }

            # Add processed_at timestamp to each page analysis
            if "image_analyses" in analysis_data:
                current_time = datetime.now().isoformat()
                for page_analysis in analysis_data["image_analyses"]:
                    page_analysis["processed_at"] = current_time

            # Create filename
            filename = f"{session_id}_analysis.json"
            file_path = self.storage_dir / filename

            # Save to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Analysis saved to {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Error saving analysis to JSON: {str(e)}")
            raise

    def load_document_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load document analysis from JSON file"""
        try:
            filename = f"{session_id}_analysis.json"
            file_path = self.storage_dir / filename

            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)

            logger.info(f"Analysis loaded from {file_path}")
            return analysis_data

        except Exception as e:
            logger.error(f"Error loading analysis from JSON: {str(e)}")
            return None

    def get_analysis_file_path(self, session_id: str) -> str:
        """Get the file path for a session's analysis"""
        filename = f"{session_id}_analysis.json"
        return str(self.storage_dir / filename)

    def analysis_exists(self, session_id: str) -> bool:
        """Check if analysis file exists for session"""
        filename = f"{session_id}_analysis.json"
        file_path = self.storage_dir / filename
        return file_path.exists()

    def delete_analysis(self, session_id: str) -> bool:
        """Delete analysis file for session"""
        try:
            filename = f"{session_id}_analysis.json"
            file_path = self.storage_dir / filename

            if file_path.exists():
                file_path.unlink()
                logger.info(f"Analysis file deleted: {file_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting analysis file: {str(e)}")
            return False

    def list_all_analyses(self) -> list:
        """List all analysis files"""
        try:
            analyses = []
            for file_path in self.storage_dir.glob("*_analysis.json"):
                session_id = file_path.stem.replace("_analysis", "")
                analyses.append(
                    {
                        "session_id": session_id,
                        "file_path": str(file_path),
                        "created_at": datetime.fromtimestamp(
                            file_path.stat().st_ctime
                        ).isoformat(),
                    }
                )
            return analyses
        except Exception as e:
            logger.error(f"Error listing analyses: {str(e)}")
            return []

    def update_page_analysis(
        self, session_id: str, page_number: int, new_analysis: str
    ) -> bool:
        """Update analysis for a specific page"""
        try:
            analysis_data = self.load_document_analysis(session_id)
            if not analysis_data:
                return False

            # Find and update the specific page
            if "image_analyses" in analysis_data:
                for page_analysis in analysis_data["image_analyses"]:
                    if page_analysis["page_number"] == page_number:
                        page_analysis["image_analysis"] = new_analysis
                        page_analysis["updated_at"] = datetime.now().isoformat()
                        break

                # Save updated data
                self.save_document_analysis(session_id, analysis_data)
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating page analysis: {str(e)}")
            return False
