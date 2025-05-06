import sys
import os
import requests
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, 
                            QFrame, QGridLayout, QSplitter, QMessageBox, QProgressBar,
                            QScrollArea, QDialog)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPalette

# ====================================================
# CONSTANTS AND CONFIGURATIONS
# ====================================================

# Region mappings for Riot API
REGIONS = {
    "EUW": ("europe", "euw1"),
    "EUNE": ("europe", "eun1"),
    "NA": ("americas", "na1"),
    "KR": ("asia", "kr"),
    "JP": ("asia", "jp1"),
    "BR": ("americas", "br1"),
    "OCE": ("americas", "oc1"),
    "TR": ("europe", "tr1"),
    "RU": ("europe", "ru"),
    "LAS": ("americas", "la2"),
    "LAN": ("americas", "la1")
}

# Position mapping for League of Legends roles
POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
POSITION_DISPLAY = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "MID",
    "BOTTOM": "adc",
    "UTILITY": "supp"
}

# Queue ID to game type mapping
QUEUE_TYPES = {
    400: "Normal Draft",
    420: "Ranked Solo/Duo",
    430: "Normal Blind",
    440: "Ranked Flex",
    700: "Clash"
}

# ====================================================
# POPUP WINDOW FOR TEAM QUALITY ASSESSMENT
# ====================================================

class QualityPopupWindow(QDialog):
    """Popup window to display team quality images"""
    def __init__(self, quality_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Team Quality: {quality_type.upper()}")
        self.setMinimumSize(500, 400)
        
        # Set dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D30;
                color: #FFFFFF;
            }
        """)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Image label
        image_label = QLabel()
        
        # Try to load image from file
        image_path = f"images/{quality_type}.jpg"
        if os.path.exists(image_path):
            # Load actual image file
            pixmap = QPixmap(image_path)
            image_label.setPixmap(pixmap)
            image_label.setScaledContents(True)
        else:
            # Create colored placeholder if image doesn't exist
            placeholder = QPixmap(400, 300)
            
            # Different color based on quality type
            if quality_type == "amazing":
                placeholder.fill(QColor("#4CAF50"))  # Green
            elif quality_type == "good":
                placeholder.fill(QColor("#8BC34A"))  # Light green
            elif quality_type == "average":
                placeholder.fill(QColor("#FFC107"))  # Amber
            elif quality_type == "below_average":
                placeholder.fill(QColor("#FF9800"))  # Orange
            else:  # bad
                placeholder.fill(QColor("#F44336"))  # Red
                
            # Set placeholder to label
            image_label.setPixmap(placeholder)
        
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label)
        
        # Add quality text based on assessment
        if quality_type == "amazing":
            quality_text = "AMAZING! Your teammates were exceptional!"
        elif quality_type == "good":
            quality_text = "GOOD! Your teammates performed well."
        elif quality_type == "average":
            quality_text = "AVERAGE. Your teammates were on par with enemies."
        elif quality_type == "below_average":
            quality_text = "BELOW AVERAGE. Your teammates struggled a bit."
        else:
            quality_text = "BAD! Your teammates were significantly underperforming."
            
        text_label = QLabel(quality_text)
        text_label.setFont(QFont("Arial", 14, QFont.Bold))
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label)
        
        # Add a close button
        close_button = QPushButton("Close")
        close_button.setMinimumHeight(40)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #0A8754;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0CA66A;
            }
            QPushButton:pressed {
                background-color: #086642;
            }
        """)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

# ====================================================
# RIOT API WORKER THREAD
# ====================================================

class ApiWorker(QThread):
    """
    Worker thread to handle API requests to Riot Games API
    Prevents UI freezing during data fetching
    """
    finished = pyqtSignal(list)    # Signal emitted when all processing is done
    error = pyqtSignal(str)        # Signal emitted when an error occurs
    progress = pyqtSignal(int)     # Signal to update progress bar
    
    def __init__(self, api_key, nick, tag, region, platform, match_count):
        super().__init__()
        self.api_key = api_key
        self.nick = nick
        self.tag = tag
        self.region = region
        self.platform = platform
        self.match_count = match_count
        
    def run(self):
        """Main method that runs in a separate thread"""
        try:
            # Step 1: Get PUUID (unique player identifier)
            self.progress.emit(5)
            puuid = self.get_puuid(self.nick, self.tag)
            if not puuid:
                self.error.emit("Could not retrieve player PUUID. Check your Riot ID and API key.")
                return
                
            self.progress.emit(10)
            
            # Step 2: Get match IDs - request double the amount to account for filtered games
            # We need more because some games might be filtered out (ARAM, TFT, etc.)
            request_count = self.match_count * 2
            match_ids = self.get_match_ids(puuid, request_count)
            if not match_ids:
                self.error.emit("No matches found for this player.")
                return
                
            self.progress.emit(30)
            
            # Step 3: Get match details for each match
            results = []
            for idx, match_id in enumerate(match_ids):
                # Update progress for each match
                progress = 30 + int((idx + 1) / len(match_ids) * 70)
                self.progress.emit(progress)
                
                # Get match data and add to results if valid
                match_data = self.get_match_details(puuid, match_id)
                if match_data:
                    results.append(match_data)
                    # Stop once we've reached the desired count
                    if len(results) >= self.match_count:
                        break
                        
            # Check if we found any valid matches
            if not results:
                self.error.emit("No valid Summoner's Rift matches found for this player.")
                return
                
            # Success! Send the results back
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"An error occurred: {str(e)}")
            
    def get_puuid(self, nick, tag):
        """Get PUUID (player unique ID) from Riot API using summoner name and tag"""
        url = f"https://{self.region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{nick}/{tag}"
        headers = {"X-Riot-Token": self.api_key}
        response = requests.get(url, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            return response.json()['puuid']
        else:
            print(f"Error retrieving PUUID: {response.status_code} - {response.text}")
            return None
            
    def get_match_ids(self, puuid, count=10):
        """Get list of match IDs for a player"""
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}"
        headers = {"X-Riot-Token": self.api_key}
        response = requests.get(url, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error retrieving match IDs: {response.status_code} - {response.text}")
            return []
            
    def get_match_details(self, puuid, match_id):
        """Get detailed match data for a specific match ID"""
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        headers = {
            "X-Riot-Token": self.api_key,
            "User-Agent": "Mozilla/5.0"  # Some APIs require a user agent
        }
        response = requests.get(url, headers=headers)
        
        # Check if request was successful
        if response.status_code != 200:
            print(f"Error retrieving match {match_id}: {response.status_code}")
            return None
            
        # Parse the match data
        data = response.json()
        players = data["info"]["participants"]
        
        # Skip non-Summoner's Rift games
        map_id = data["info"]["mapId"]
        if map_id != 11:  # 11 is Summoner's Rift
            return None
            
        # Skip ARAM, TFT, and other non-standard modes
        queue_id = data["info"]["queueId"]
        if queue_id in [450, 1090, 1100, 1110, 1130, 1150, 1200]:  # ARAM and various TFT queues
            return None
        
        # Divide players into teams
        team1 = [p for p in players if p["teamId"] == 100]  # Blue team
        team2 = [p for p in players if p["teamId"] == 200]  # Red team
        
        # Determine which team the player is on
        player_team = 1 if any(p["puuid"] == puuid for p in team1) else 2
        allied_team = team1 if player_team == 1 else team2
        enemy_team = team2 if player_team == 1 else team1
        
        # Sort players by position for better display
        allied_by_position = {}
        enemy_by_position = {}
        
        for position in POSITIONS:
            allied_by_position[position] = next((p for p in allied_team if p.get("teamPosition") == position), None)
            enemy_by_position[position] = next((p for p in enemy_team if p.get("teamPosition") == position), None)
        
        # Get match time in minutes
        game_duration = data["info"]["gameDuration"] / 60  # Convert to minutes
        
        # Get game result for player
        player = next((p for p in players if p["puuid"] == puuid), None)
        win = player["win"] if player else False
        
        # Get match type/mode from queue ID
        queue_id = data["info"]["queueId"]
        game_type = QUEUE_TYPES.get(queue_id, "Summoner's Rift")  # Default if unknown queue type
        
        # Return structured match data
        return {
            "match_id": match_id,
            "duration": game_duration,
            "win": win,
            "game_type": game_type,
            "queue_id": queue_id,
            "game_version": data["info"]["gameVersion"],
            "player": player,
            "allied_team": allied_team,
            "enemy_team": enemy_team,
            "allied_by_position": allied_by_position,
            "enemy_by_position": enemy_by_position
        }

# ====================================================
# MATCH CARD WIDGET - DISPLAYS A SINGLE MATCH
# ====================================================

class MatchCardWidget(QFrame):
    """Widget to display a single match's data in a card format"""
    def __init__(self, match_data, user_puuid, parent=None):
        super().__init__(parent)
        self.match_data = match_data
        self.user_puuid = user_puuid
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize and configure the UI components"""
        # Set frame style
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet("""
            MatchCardWidget {
                background-color: #1E1E1E;
                border: 2px solid #3F3F3F;
                border-radius: 6px;
                margin: 10px;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        
        # Header with game info
        header_layout = QHBoxLayout()
        
        # Game type and result
        game_result = "Victory" if self.match_data["win"] else "Defeat"
        result_color = "#4CAF50" if self.match_data["win"] else "#F44336"  # Green for win, red for loss
        
        game_info = QLabel(f"{self.match_data['game_type']} - {game_result} ({self.match_data['duration']:.1f} min)")
        game_info.setFont(QFont("Arial", 12, QFont.Bold))
        game_info.setStyleSheet(f"color: {result_color};")
        header_layout.addWidget(game_info)
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # Team title label
        my_team_label = QLabel("MY TEAM")
        my_team_label.setFont(QFont("Arial", 16, QFont.Bold))
        my_team_label.setAlignment(Qt.AlignCenter)
        my_team_label.setStyleSheet("background-color: #2D2D30; padding: 5px;")
        main_layout.addWidget(my_team_label)
        
        # Position layout - creates boxes for each role
        positions_layout = QHBoxLayout()
        positions_layout.setSpacing(5)
        
        # Create position boxes for each role (TOP, JUNGLE, MID, ADC, SUPPORT)
        for position in POSITIONS:
            position_frame = self.create_position_frame(position)
            positions_layout.addWidget(position_frame)
            
        main_layout.addLayout(positions_layout)
        
        # Damage chart showing damage dealt by each player
        damage_frame = self.create_damage_chart()
        main_layout.addWidget(damage_frame)
        
        # Enemy team label
        enemy_label = QLabel("ENEMY TEAM")
        enemy_label.setFont(QFont("Arial", 16, QFont.Bold))
        enemy_label.setAlignment(Qt.AlignCenter)
        enemy_label.setStyleSheet("background-color: #2D2D30; padding: 5px;")
        main_layout.addWidget(enemy_label)
        
    def create_position_frame(self, position):
        """Create frame showing player data for a specific position"""
        # Create a frame for the position
        position_frame = QFrame()
        position_frame.setFrameShape(QFrame.Box)
        position_frame.setLineWidth(1)
        position_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #4f4f4f;
                background-color: #2D2D30;
            }
        """)
        
        # Layout for the position frame
        position_layout = QVBoxLayout(position_frame)
        position_layout.setContentsMargins(8, 5, 8, 5)
        position_layout.setSpacing(2)
        
        # Get ally and enemy players for this position
        ally = self.match_data["allied_by_position"].get(position)
        enemy = self.match_data["enemy_by_position"].get(position)
        
        # Ally KDA at the top
        if ally:
            is_user = ally["puuid"] == self.user_puuid
            ally_label = QLabel(self.format_ally_kda(ally, is_user))
            ally_label.setAlignment(Qt.AlignCenter)
            if is_user:
                ally_label.setStyleSheet("color: #FFEB3B; font-size: 10pt; font-weight: bold;")  # Yellow for user
            else:
                ally_label.setStyleSheet("color: #8BC34A; font-size: 10pt;")  # Green for ally
            position_layout.addWidget(ally_label)
        else:
            position_layout.addWidget(QLabel(""))  # Empty placeholder
        
        # Position label in the middle
        pos_display = POSITION_DISPLAY.get(position, position)
        pos_label = QLabel(pos_display)
        pos_label.setFont(QFont("Arial", 14, QFont.Bold))
        pos_label.setAlignment(Qt.AlignCenter)
        pos_label.setStyleSheet("color: white;")
        position_layout.addWidget(pos_label)
        
        # Enemy KDA at the bottom
        if enemy:
            enemy_label = QLabel(self.format_enemy_kda(enemy))
            enemy_label.setAlignment(Qt.AlignCenter)
            enemy_label.setStyleSheet("color: #F44336; font-size: 10pt;")  # Red for enemy
            position_layout.addWidget(enemy_label)
        else:
            position_layout.addWidget(QLabel(""))  # Empty placeholder
            
        return position_frame
        
    def format_ally_kda(self, player, is_user=False):
        """Format KDA display for allied players"""
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        assists = player.get("assists", 0)
        champion = player.get("championName", "Unknown")
        
        kda_ratio = (kills + assists) / max(1, deaths)  # Avoid division by zero
        
        # Format display with champion name and KDA stats
        return f"{champion}\n{kills}/{deaths}/{assists}\nKDA: {kda_ratio:.1f}"
        
    def format_enemy_kda(self, player):
        """Format KDA display for enemy players"""
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        assists = player.get("assists", 0)
        champion = player.get("championName", "Unknown")
        
        kda_ratio = (kills + assists) / max(1, deaths)  # Avoid division by zero
        
        # Format display with champion name and KDA stats
        return f"{champion}\n{kills}/{deaths}/{assists}\nKDA: {kda_ratio:.1f}"
        
    def create_damage_chart(self):
        """Create a frame showing damage dealt by each player"""
        # Create frame for damage chart
        damage_frame = QFrame()
        damage_frame.setFrameShape(QFrame.Box)
        damage_frame.setLineWidth(1)
        damage_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #4f4f4f;
                background-color: #2D2D30;
                padding: 5px;
            }
        """)
        
        # Layout for damage chart
        damage_layout = QVBoxLayout(damage_frame)
        damage_layout.setContentsMargins(8, 5, 8, 5)
        damage_layout.setSpacing(2)
        
        # Title
        title_label = QLabel("Damage to Champions")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        damage_layout.addWidget(title_label)
        
        # Get all players from both teams
        allies = self.match_data["allied_team"]
        enemies = self.match_data["enemy_team"]
        all_players = allies + enemies
        
        # Find max damage to scale progress bars
        max_damage = max(p.get("totalDamageDealtToChampions", 0) for p in all_players)
        
        # Create bars for allied players
        for player in allies:
            player_damage = player.get("totalDamageDealtToChampions", 0)
            is_user = player["puuid"] == self.user_puuid
            champion = player.get("championName", "Unknown")
            
            # Format: (ChampionName): damage_value
            if is_user:
                name_label = QLabel(f"({champion}): {player_damage:,}")
                name_label.setStyleSheet("color: #FFEB3B; font-weight: bold;")  # Yellow for user
            else:
                name_label = QLabel(f"({champion}): {player_damage:,}")
                name_label.setStyleSheet("color: #8BC34A;")  # Green for ally
            
            damage_layout.addWidget(name_label)
            
            # Progress bar for damage
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setMaximum(max_damage)
            bar.setValue(player_damage)
            
            if is_user:
                bar.setStyleSheet("""
                    QProgressBar {
                        border: 1px solid #5f5f5f;
                        border-radius: 2px;
                        background-color: #3f3f3f;
                        height: 10px;
                    }
                    QProgressBar::chunk {
                        background-color: #FFEB3B;
                    }
                """)
            else:
                bar.setStyleSheet("""
                    QProgressBar {
                        border: 1px solid #5f5f5f;
                        border-radius: 2px;
                        background-color: #3f3f3f;
                        height: 10px;
                    }
                    QProgressBar::chunk {
                        background-color: #8BC34A;
                    }
                """)
            
            damage_layout.addWidget(bar)
            
        # Create bars for enemy players
        for player in enemies:
            player_damage = player.get("totalDamageDealtToChampions", 0)
            champion = player.get("championName", "Unknown")
            
            # Format: (ChampionName): damage_value
            name_label = QLabel(f"({champion}): {player_damage:,}")
            name_label.setStyleSheet("color: #F44336;")  # Red for enemy
            
            damage_layout.addWidget(name_label)
            
            # Progress bar for damage
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setMaximum(max_damage)
            bar.setValue(player_damage)
            
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #5f5f5f;
                    border-radius: 2px;
                    background-color: #3f3f3f;
                    height: 10px;
                }
                QProgressBar::chunk {
                    background-color: #F44336;
                }
            """)
            
            damage_layout.addWidget(bar)
        
        return damage_frame

# ====================================================
# MAIN APPLICATION WINDOW
# ====================================================

class TeamAnalyzerApp(QMainWindow):
    """Main application window for League of Legends Team Analyzer"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("How Bad Is Your Team? - LoL Analyzer")
        self.setMinimumSize(1200, 800)
        
        # Apply dark theme to the application
        self.apply_dark_theme()
        
        # Setup the main UI components
        self.setup_ui()
        
        # Worker thread for API requests
        self.worker = None
        
    def setup_ui(self):
        """Set up the main user interface"""
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Header with logo
        header_layout = QHBoxLayout()
        logo_label = QLabel("🎮 How Bad Is Your Team?")
        logo_label.setFont(QFont("Arial", 18, QFont.Bold))
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Form layout for input fields
        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(10)
        
        # API Key input
        form_layout.addWidget(QLabel("Riot API Key:"), 0, 0)
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter your Riot API Key")
        self.api_input.setEchoMode(QLineEdit.Password)  # Hide API key
        form_layout.addWidget(self.api_input, 1, 0)
        
        # Summoner name input
        form_layout.addWidget(QLabel("Summoner Name:"), 0, 1)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your Riot ID (e.g. T1 sosa)")
        form_layout.addWidget(self.name_input, 1, 1)
        
        # Tag input
        form_layout.addWidget(QLabel("Tag:"), 0, 2)
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag (e.g. win)")
        form_layout.addWidget(self.tag_input, 1, 2)
        
        # Region selection
        form_layout.addWidget(QLabel("Region:"), 0, 3)
        self.region_combo = QComboBox()
        for region in REGIONS.keys():
            self.region_combo.addItem(region)
        form_layout.addWidget(self.region_combo, 1, 3)
        
        # Match count selection
        form_layout.addWidget(QLabel("Number of Matches:"), 0, 4)
        self.count_combo = QComboBox()
        for count in [5, 10, 15, 20]:
            self.count_combo.addItem(str(count))
        self.count_combo.setCurrentIndex(1)  # Default to 10
        form_layout.addWidget(self.count_combo, 1, 4)
        
        # Analyze button
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setMinimumHeight(40)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #0A8754;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0CA66A;
            }
            QPushButton:pressed {
                background-color: #086642;
            }
        """)
        self.analyze_button.clicked.connect(self.start_analysis)
        form_layout.addWidget(self.analyze_button, 2, 0, 1, 5)
        
        main_layout.addLayout(form_layout)
        
        # Progress bar for loading status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Create a scroll area for match cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2D2D30;
            }
        """)
        
        # Container widget for match cards
        self.match_container = QWidget()
        self.match_layout = QVBoxLayout(self.match_container)
        self.match_layout.setAlignment(Qt.AlignTop)
        self.match_layout.setContentsMargins(10, 10, 10, 10)
        self.match_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.match_container)
        main_layout.addWidget(self.scroll_area)
        
        # Status bar for app state messages
        self.statusBar().showMessage("Ready")
        
    def show_quality_popup(self, quality_type):
        """Show a popup window with an image based on team quality"""
        popup = QualityPopupWindow(quality_type, self)
        popup.show()
        
    def apply_dark_theme(self):
        """Apply dark theme colors to the application"""
        dark_palette = QPalette()
        
        # Set color scheme for dark theme
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        
        self.setPalette(dark_palette)
        
        # Set stylesheet for widgets
        self.setStyleSheet("""
            QWidget {
                background-color: #2D2D30;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit, QComboBox {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3F3F3F;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox::down-arrow {
                image: url(dropdown-arrow.png);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                color: #FFFFFF;
                selection-background-color: #0A8754;
            }
            QScrollBar:vertical {
                border: none;
                background: #2D2D30;
                width: 14px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #5D5D60;
                min-height: 20px;
                border-radius: 7px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
    def start_analysis(self):
        """Start the analysis process when the Analyze button is clicked"""
        # Get input values from form fields
        api_key = self.api_input.text().strip()
        nick = self.name_input.text().strip()
        tag = self.tag_input.text().strip()
        region_key = self.region_combo.currentText()
        region, platform = REGIONS[region_key]
        match_count = int(self.count_combo.currentText())
        
        # Validate inputs
        if not api_key or not nick or not tag:
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")
            return
            
        # Clear previous results
        self.clear_matches()
        
        # Update UI state to show loading
        self.analyze_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("Analyzing...")
        
        # Create and start worker thread
        self.worker = ApiWorker(api_key, nick, tag, region, platform, match_count)
        self.worker.finished.connect(self.display_results)
        self.worker.error.connect(self.show_error)
        self.worker.progress.connect(self.update_progress)
        self.worker.start()
        
    def update_progress(self, value):
        """Update the progress bar value"""
        self.progress_bar.setValue(value)
        
    def show_error(self, message):
        """Show error message if something goes wrong"""
        QMessageBox.critical(self, "Error", message)
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Analysis failed")
        
    def clear_matches(self):
        """Clear all previous match cards from display"""
        while self.match_layout.count():
            item = self.match_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
    def display_results(self, matches):
        """Display analysis results for all matches"""
        if not matches:
            QMessageBox.information(self, "No Data", "No matches found to analyze.")
            self.analyze_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.statusBar().showMessage("Ready")
            return
        
        # Get the user's PUUID for highlighting their performance
        user_puuid = matches[0]["player"]["puuid"]
        
        # Add stats summary at the top
        summary_frame = self.create_summary_frame(matches)
        self.match_layout.addWidget(summary_frame)
            
        # Add match cards for each match
        for match in matches:
            match_card = MatchCardWidget(match, user_puuid)
            self.match_layout.addWidget(match_card)
            
        # Re-enable UI elements
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Analysis complete")
        
    def create_summary_frame(self, matches):
        """Create a summary frame with overall stats and team quality assessment"""
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Box)
        summary_frame.setLineWidth(2)
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 2px solid #3F3F3F;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(summary_frame)
        
        # Get player name
        player_name = matches[0]["player"]["summonerName"]
        
        # Title
        title = QLabel(f"Analysis Results for {player_name}")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Stats layout
        stats_layout = QHBoxLayout()
        
        # Calculate win rate
        total_matches = len(matches)
        wins = sum(1 for match in matches if match["win"])
        win_rate = (wins / total_matches) * 100
        
        # Win rate label
        win_label = QLabel(f"Win Rate: {wins}/{total_matches} ({win_rate:.1f}%)")
        win_label.setFont(QFont("Arial", 12))
        stats_layout.addWidget(win_label)
        
        # Calculate KDAs
        player_kills = sum(match["player"]["kills"] for match in matches)
        player_deaths = sum(match["player"]["deaths"] for match in matches)
        player_assists = sum(match["player"]["assists"] for match in matches)
        player_kda = (player_kills + player_assists) / max(1, player_deaths)
        
        # KDA label
        kda_label = QLabel(f"Overall KDA: {player_kills}/{player_deaths}/{player_assists} ({player_kda:.2f})")
        kda_label.setFont(QFont("Arial", 12))
        stats_layout.addWidget(kda_label)
        
        layout.addLayout(stats_layout)
        
        # Team quality assessment
        team_kdas = []
        enemy_kdas = []
        
        # Collect KDA data from all matches
        for match in matches:
            # Team stats (excluding player)
            allies = [p for p in match["allied_team"] if p["puuid"] != match["player"]["puuid"]]
            for ally in allies:
                ally_kda = (ally["kills"] + ally["assists"]) / max(1, ally["deaths"])
                team_kdas.append(ally_kda)
                
            # Enemy stats
            for enemy in match["enemy_team"]:
                enemy_kda = (enemy["kills"] + enemy["assists"]) / max(1, enemy["deaths"])
                enemy_kdas.append(enemy_kda)
        
        # Calculate average KDAs
        avg_team_kda = sum(team_kdas) / len(team_kdas) if team_kdas else 0
        avg_enemy_kda = sum(enemy_kdas) / len(enemy_kdas) if enemy_kdas else 0
        
        # Team quality assessment
        team_quality = avg_team_kda / avg_enemy_kda if avg_enemy_kda > 0 else 0
        
        assessment_layout = QHBoxLayout()
        
        team_label = QLabel(f"Team Avg KDA: {avg_team_kda:.2f}")
        team_label.setFont(QFont("Arial", 12))
        assessment_layout.addWidget(team_label)
        
        enemy_label = QLabel(f"Enemy Avg KDA: {avg_enemy_kda:.2f}")
        enemy_label.setFont(QFont("Arial", 12))
        assessment_layout.addWidget(enemy_label)
        
        layout.addLayout(assessment_layout)
        
        # Determine quality level based on team quality ratio
        if team_quality >= 1.3:
            assessment = "AMAZING - You have exceptional teammates!"
            quality_type = "amazing"
        elif team_quality >= 1.1:
            assessment = "GOOD - Your teammates are performing well"
            quality_type = "good"
        elif team_quality >= 0.9:
            assessment = "AVERAGE - Your teammates are on par with enemies"
            quality_type = "average"
        elif team_quality >= 0.7:
            assessment = "BELOW AVERAGE - Your teammates are struggling a bit"
            quality_type = "below_average"
        else:
            assessment = "BAD - Your teammates are significantly underperforming"
            quality_type = "bad"
            
        quality_label = QLabel(f"Team Quality: {assessment} (Ratio: {team_quality:.2f})")
        quality_label.setFont(QFont("Arial", 12, QFont.Bold))
        quality_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(quality_label)
        
        # Show popup with quality image
        self.show_quality_popup(quality_type)
        
        return summary_frame

# ====================================================
# APPLICATION ENTRY POINT
# ====================================================

if __name__ == "__main__":
    # Create QApplication instance
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = TeamAnalyzerApp()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())