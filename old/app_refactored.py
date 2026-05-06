import os
import time
import json
import threading
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from threading import Thread

from flask import Flask, request, jsonify
from flask_cors import CORS
import datajoint as dj
import pymysql

# Import custom functions
from helpers.init import create_database, delete_database, start_database, stop_database
from helpers.pop import append_data
from helpers.query import (
    saved_queries, add_query, delete_query, query_levels, table_fields, 
    create_query, generate_tree, get_metadata_helper, get_options, 
    get_trace_binary, get_spikehist_binary, add_tags, delete_tags,
    push_tags, pull_tags, reset_tags
)


@dataclass
class AppConfig:
    """Configuration class for the application settings."""
    home_dir: str = os.getcwd()
    schema_path: str = './api/schema.py'
    db_dir: str = os.path.abspath("../databases")
    download_dir: str = os.path.abspath("../downloads")
    host_address: str = '127.0.0.1'
    user: str = 'root'
    password: str = 'simple'


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.db: Optional[dj.VirtualModule] = None
        self._setup_datajoint_config()
    
    def _setup_datajoint_config(self):
        """Configure DataJoint connection settings."""
        dj.config["database.host"] = self.config.host_address
        dj.config["database.user"] = self.config.user
        dj.config["database.password"] = self.config.password
        print("DataJoint configuration set", flush=True)
    
    def connect_to_database(self, db_name: str) -> bool:
        """Connect to a specific database."""
        if not db_name or not self.config.db_dir:
            return False
        
        try:
            # Attempt connection with retries
            for attempt in range(4):
                try:
                    if not dj.conn().is_connected:
                        dj.conn().connect()
                except pymysql.OperationalError as e:
                    print(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(1)
            
            if not dj.conn().is_connected:
                dj.conn().connect()
            
            print('Connected' if dj.conn().is_connected else 'Failed to connect', flush=True)
            
            # Initialize schema if needed
            if 'schema' not in dj.list_schemas():
                print('Initializing schema')
                exec(open(self.config.schema_path).read())
            
            self.db = dj.VirtualModule('schema.py', 'schema')
            return True
            
        except Exception as e:
            print(f"Error connecting to database: {e}", flush=True)
            return False
    
    def disconnect(self):
        """Disconnect from the current database."""
        if self.db and dj.conn().is_connected:
            dj.conn().close()
            self.db = None
    
    def is_connected(self) -> bool:
        """Check if connected to a database."""
        return self.db is not None
    
    def get_database(self) -> Optional[dj.VirtualModule]:
        """Get the current database connection."""
        return self.db


class UserManager:
    """Manages user authentication and session."""
    
    def __init__(self):
        self.username: Optional[str] = None
    
    def set_user(self, username: str) -> bool:
        """Set the current user."""
        if username and '/' not in username and username != "user_not_set":
            self.username = username
            return True
        else:
            self.username = None
            return False
    
    def get_user(self) -> str:
        """Get the current user."""
        return self.username if self.username else "user_not_set"
    
    def is_user_set(self) -> bool:
        """Check if a user is set."""
        return self.username is not None


class DataManager:
    """Manages data operations and progress tracking."""
    
    def __init__(self, db_manager: DatabaseManager, user_manager: UserManager):
        self.db_manager = db_manager
        self.user_manager = user_manager
        self.add_data_started = False
        self.add_data_error: Optional[str] = None
    
    def is_empty(self) -> Dict[str, Any]:
        """Check if the database is empty."""
        db = self.db_manager.get_database()
        if not db:
            return {"error": "No database connection!"}
        
        try:
            num_experiments = len((db.Experiment & "id>=1").fetch())
            return {
                "empty": num_experiments == 0,
                "num_experiments": num_experiments
            }
        except Exception as e:
            return {"error": f"Error checking database: {e}"}
    
    def add_data(self, data_dir: str, meta_dir: str, tags_dir: str) -> Dict[str, Any]:
        """Add data to the database."""
        if not self.db_manager.is_connected() or not self.user_manager.is_user_set():
            return {"error": "Connect and sign in first!"}
        
        if self.add_data_started:
            return {"error": "Data addition already in progress!"}
        
        try:
            Thread(
                target=self._add_data_thread,
                args=(data_dir, meta_dir, tags_dir)
            ).start()
            return {"message": "Successfully started adding data! This can take a while."}
        except Exception as e:
            return {"error": f"Error adding to database: {e}"}
    
    def _add_data_thread(self, data_dir: str, meta_dir: str, tags_dir: str):
        """Background thread for adding data."""
        self.add_data_started = True
        self.add_data_error = None
        
        try:
            db = self.db_manager.get_database()
            username = self.user_manager.get_user()
            append_data(data_dir, meta_dir, tags_dir, username, db)
        except Exception as e:
            print(f"Error adding to database: {e}", flush=True)
            self.add_data_error = str(e)
        finally:
            self.add_data_started = False
    
    def is_adding(self) -> Dict[str, Any]:
        """Check if data addition is in progress."""
        if self.add_data_error:
            return {"error": self.add_data_error}
        return {"adding": self.add_data_started}
    
    def clear_data(self) -> Dict[str, Any]:
        """Clear all data from the database."""
        db = self.db_manager.get_database()
        if not db:
            return {"error": "No database connection!"}
        
        try:
            # Clear all tables in reverse dependency order
            tables_to_clear = [
                'Tags', 'Stimulus', 'Response', 'Epoch', 'EpochBlock',
                'SortedCellType', 'CellTypeFile', 'SortedCell', 'SortingChunk',
                'EpochGroup', 'Cell', 'Preparation', 'Animal', 'Experiment'
            ]
            
            for table_name in tables_to_clear:
                table = getattr(db, table_name, None)
                if table:
                    table.delete()
            
            return {"message": "Database cleared successfully!"}
        except Exception as e:
            return {"error": f"Error clearing database: {e}"}


class QueryManager:
    """Manages database queries and saved queries."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.query: Optional[dj.expression.QueryExpression] = None
        self.exclude_levels: List[str] = []
    
    def get_query_levels(self) -> Dict[str, Any]:
        """Get available query levels."""
        try:
            levels = query_levels()
            return {"levels": levels}
        except Exception as e:
            return {"error": f"Error getting query levels: {e}"}
    
    def get_table_fields(self, table_name: str) -> Dict[str, Any]:
        """Get fields for a specific table."""
        try:
            fields = table_fields(table_name)
            return {"fields": fields}
        except Exception as e:
            return {"error": f"Error getting table fields: {e}"}
    
    def get_levels_and_fields(self) -> Dict[str, Any]:
        """Get both levels and fields."""
        try:
            levels = query_levels()
            fields = {}
            for level in levels:
                fields[level] = table_fields(level)
            return {"levels": levels, "fields": fields}
        except Exception as e:
            return {"error": f"Error getting levels and fields: {e}"}
    
    def get_saved_queries(self) -> Dict[str, Any]:
        """Get saved queries."""
        try:
            queries = saved_queries()
            return {"queries": queries}
        except Exception as e:
            return {"error": f"Error getting saved queries: {e}"}
    
    def add_saved_query(self, name: str, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a saved query."""
        try:
            add_query(name, query_data)
            return {"message": "Query saved successfully!"}
        except Exception as e:
            return {"error": f"Error saving query: {e}"}
    
    def delete_saved_query(self, name: str) -> Dict[str, Any]:
        """Delete a saved query."""
        try:
            delete_query(name)
            return {"message": "Query deleted successfully!"}
        except Exception as e:
            return {"error": f"Error deleting query: {e}"}
    
    def execute_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a query."""
        try:
            self.query = create_query(query_data)
            self.exclude_levels = query_data.get('exclude_levels', [])
            return {"message": "Query executed successfully!"}
        except Exception as e:
            return {"error": f"Error executing query: {e}"}
    
    def get_query_tree(self) -> Dict[str, Any]:
        """Get the query tree structure."""
        if not self.query:
            return {"error": "No active query!"}
        
        try:
            tree = generate_tree(self.query, self.exclude_levels)
            return {"tree": tree}
        except Exception as e:
            return {"error": f"Error generating tree: {e}"}


class ResultsManager:
    """Manages query results and data export."""
    
    def __init__(self, db_manager: DatabaseManager, query_manager: QueryManager, config: AppConfig):
        self.db_manager = db_manager
        self.query_manager = query_manager
        self.config = config
    
    def download_results(self, filename: str, include_meta: bool = False) -> Dict[str, Any]:
        """Download query results."""
        if not self.query_manager.query:
            return {"error": "No active query!"}
        
        try:
            def download_thread():
                try:
                    # Implementation would go here
                    pass
                except Exception as e:
                    print(f"Error in download thread: {e}", flush=True)
            
            Thread(target=download_thread).start()
            return {"message": "Download started successfully!"}
        except Exception as e:
            return {"error": f"Error starting download: {e}"}
    
    def get_metadata(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get metadata for query results."""
        try:
            metadata = get_metadata_helper(self.query_manager.query, query_data)
            return {"metadata": metadata}
        except Exception as e:
            return {"error": f"Error getting metadata: {e}"}
    
    def get_visualization_data(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for visualization."""
        try:
            # Implementation would depend on specific visualization needs
            return {"data": "visualization_data"}
        except Exception as e:
            return {"error": f"Error getting visualization data: {e}"}
    
    def get_visualization(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get visualization options."""
        try:
            options = get_options(self.query_manager.query, query_data)
            return {"options": options}
        except Exception as e:
            return {"error": f"Error getting visualization options: {e}"}
    
    def add_tags(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add tags to results."""
        try:
            add_tags(self.query_manager.query, tag_data)
            return {"message": "Tags added successfully!"}
        except Exception as e:
            return {"error": f"Error adding tags: {e}"}
    
    def delete_tags(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete tags from results."""
        try:
            delete_tags(self.query_manager.query, tag_data)
            return {"message": "Tags deleted successfully!"}
        except Exception as e:
            return {"error": f"Error deleting tags: {e}"}
    
    def push_tags(self, filename: str) -> Dict[str, Any]:
        """Export tags to file."""
        try:
            push_tags(self.query_manager.query, filename)
            return {"message": "Tags exported successfully!"}
        except Exception as e:
            return {"error": f"Error exporting tags: {e}"}
    
    def pull_tags(self, filename: str) -> Dict[str, Any]:
        """Import tags from file."""
        try:
            pull_tags(self.query_manager.query, filename)
            return {"message": "Tags imported successfully!"}
        except Exception as e:
            return {"error": f"Error importing tags: {e}"}
    
    def reset_tags(self, filename: str) -> Dict[str, Any]:
        """Reset tags from file."""
        try:
            reset_tags(self.query_manager.query, filename)
            return {"message": "Tags reset successfully!"}
        except Exception as e:
            return {"error": f"Error resetting tags: {e}"}


class DataJointAPI:
    """Main API class that orchestrates all components."""
    
    def __init__(self):
        self.config = AppConfig()
        self.db_manager = DatabaseManager(self.config)
        self.user_manager = UserManager()
        self.data_manager = DataManager(self.db_manager, self.user_manager)
        self.query_manager = QueryManager(self.db_manager)
        self.results_manager = ResultsManager(self.db_manager, self.query_manager, self.config)
        
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all Flask routes."""
        
        # Database initialization routes
        @self.app.route('/init/set-database-directory', methods=['POST'])
        def set_db_dir():
            dir_path = request.json.get('dir')
            if dir_path and os.path.isdir(dir_path):
                self.config.db_dir = dir_path
                return jsonify({"message": "Database directory set successfully!"}), 200
            else:
                return jsonify({"message": "Invalid directory path!"}), 400
        
        @self.app.route('/init/set-mea-directory', methods=['POST'])
        def set_mea_dir():
            dir_path = request.json.get('dir')
            if dir_path and os.path.isdir(dir_path):
                self.config.mea_dir = dir_path
                return jsonify({"message": "MEA data directory set successfully!"}), 200
            else:
                return jsonify({"message": "Invalid directory path!"}), 400
        
        @self.app.route('/init/get-database-directory', methods=['GET'])
        def get_db_dir():
            return jsonify({"dir": self.config.db_dir})
        
        @self.app.route('/init/list-databases', methods=['GET'])
        def list_dbs():
            if self.config.db_dir:
                dbs = [f for f in os.listdir(self.config.db_dir) 
                      if os.path.isdir(os.path.join(self.config.db_dir, f))]
                return jsonify({"databases": dbs}), 200
            else:
                return jsonify({"message": "Database directory not set!"}), 400
        
        @self.app.route('/init/create-database', methods=['POST'])
        def create_db():
            db_name = request.json.get('name')
            if db_name and self.config.db_dir:
                try:
                    create_database(self.config.home_dir, self.config.db_dir, db_name)
                    return jsonify({"message": "Database created successfully!"}), 200
                except Exception as e:
                    return jsonify({"message": f"Error creating database: {e}"}), 400
            else:
                return jsonify({"message": "Invalid database name!"}), 400
        
        @self.app.route('/init/delete-database', methods=['POST'])
        def delete_db():
            db_name = request.json.get('name')
            if db_name and self.config.db_dir:
                try:
                    conn = dj.conn() if hasattr(dj.conn, 'connection') else None
                    delete_database(self.config.home_dir, self.config.db_dir, db_name, conn)
                    return jsonify({"message": "Database deleted successfully!"}), 200
                except Exception as e:
                    return jsonify({"message": f"Error deleting database: {e}"}), 400
            else:
                return jsonify({"message": "Invalid database name!"}), 400
        
        @self.app.route('/init/start-database', methods=['POST'])
        def start_db():
            db_name = request.json.get('name')
            if db_name and self.config.db_dir:
                try:
                    start_database(self.config.home_dir, self.config.db_dir, db_name)
                    return jsonify({"message": "Database started successfully!"}), 200
                except Exception as e:
                    return jsonify({"message": f"Error starting database: {e}"}), 400
            else:
                return jsonify({"message": "Invalid database name!"}), 400
        
        @self.app.route('/init/stop-database', methods=['POST'])
        def stop_db():
            db_name = request.json.get('name')
            if db_name and self.config.db_dir:
                try:
                    conn = dj.conn() if hasattr(dj.conn, 'connection') else None
                    stop_database(self.config.home_dir, self.config.db_dir, db_name, conn)
                    return jsonify({"message": "Database stopped successfully!"}), 200
                except Exception as e:
                    return jsonify({"message": f"Error stopping database: {e}"}), 400
            else:
                return jsonify({"message": "Invalid database name!"}), 400
        
        @self.app.route('/init/connect-database', methods=['POST'])
        def connect_db():
            db_name = request.json.get('name')
            if self.db_manager.connect_to_database(db_name):
                return jsonify({"message": "Connected to database successfully!"}), 200
            else:
                return jsonify({"message": "Error connecting to database!"}), 400
        
        @self.app.route('/init/is-connected', methods=['GET'])
        def is_connected():
            return jsonify({"connected": self.db_manager.is_connected()}), 200
        
        # User management routes
        @self.app.route('/user/set-user', methods=['POST'])
        def set_user():
            username = request.json.get('user')
            if self.user_manager.set_user(username):
                return jsonify({"message": "User set successfully!"}), 200
            else:
                return jsonify({"message": "Invalid user name!"}), 400
        
        @self.app.route('/user/get-user', methods=['GET'])
        def get_user():
            return jsonify({"user": self.user_manager.get_user()}), 200
        
        # Data management routes
        @self.app.route('/pop/is-empty', methods=['GET'])
        def is_empty():
            result = self.data_manager.is_empty()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/pop/add-data', methods=['POST'])
        def add_data():
            result = self.data_manager.add_data(
                request.json.get('data_dir'),
                request.json.get('meta_dir'),
                request.json.get('tags_dir')
            )
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/pop/is-adding', methods=['GET'])
        def is_adding():
            result = self.data_manager.is_adding()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/pop/clear', methods=['POST'])
        def clear_data():
            result = self.data_manager.clear_data()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        # Query management routes
        @self.app.route('/query/get-query-levels', methods=['GET'])
        def get_query_levels():
            result = self.query_manager.get_query_levels()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/get-table-fields', methods=['POST'])
        def get_table_fields():
            table_name = request.json.get('table_name')
            result = self.query_manager.get_table_fields(table_name)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/get-levels-and-fields', methods=['GET'])
        def get_levels_and_fields():
            result = self.query_manager.get_levels_and_fields()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/get-saved-queries', methods=['GET'])
        def get_saved_queries():
            result = self.query_manager.get_saved_queries()
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/add-saved-query', methods=['POST'])
        def add_saved_query():
            name = request.json.get('name')
            query_data = request.json.get('query')
            result = self.query_manager.add_saved_query(name, query_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/delete-saved-query', methods=['POST'])
        def delete_saved_query():
            name = request.json.get('name')
            result = self.query_manager.delete_saved_query(name)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/query/execute-query', methods=['POST'])
        def execute_query():
            query_data = request.json.get('query')
            result = self.query_manager.execute_query(query_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        # Results management routes
        @self.app.route('/results/download-results', methods=['POST'])
        def download_results():
            filename = request.json.get('filename')
            include_meta = request.json.get('include_meta', False)
            result = self.results_manager.download_results(filename, include_meta)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/get-metadata', methods=['POST'])
        def get_metadata():
            query_data = request.json.get('query')
            result = self.results_manager.get_metadata(query_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/get-visualization-data', methods=['POST'])
        def get_visualization_data():
            query_data = request.json.get('query')
            result = self.results_manager.get_visualization_data(query_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/get-visualization', methods=['POST'])
        def get_visualization():
            query_data = request.json.get('query')
            result = self.results_manager.get_visualization(query_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/add-tags', methods=['POST'])
        def bulk_add_tags():
            tag_data = request.json.get('tags')
            result = self.results_manager.add_tags(tag_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/delete-tags', methods=['POST'])
        def bulk_delete_tags():
            tag_data = request.json.get('tags')
            result = self.results_manager.delete_tags(tag_data)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/push-tags', methods=['POST'])
        def export_push_tags():
            filename = request.json.get('filename')
            result = self.results_manager.push_tags(filename)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/pull-tags', methods=['POST'])
        def import_pull_tags():
            filename = request.json.get('filename')
            result = self.results_manager.pull_tags(filename)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
        
        @self.app.route('/results/reset-tags', methods=['POST'])
        def import_reset_tags():
            filename = request.json.get('filename')
            result = self.results_manager.reset_tags(filename)
            if "error" in result:
                return jsonify({"message": result["error"]}), 400
            return jsonify(result), 200
    
    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the Flask application."""
        self.app.run(host=host, port=port, debug=debug)


# Create and run the application
if __name__ == '__main__':
    api = DataJointAPI()
    api.run() 