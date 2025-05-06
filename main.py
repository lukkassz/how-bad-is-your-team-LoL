import sys
import os
import requests
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, 
                            QFrame, QGridLayout, QSplitter, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPalette

# Constants
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

class ApiWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, api_key, nick, tag, region, platform, match_count):
        super().__init__()
        self.api_key = api_key
        self.nick = nick
        self.tag = tag
        self.region = region
        self.platform = platform
        self.match_count = match_count
        
    def run(self):
        try:
            # Step 1: Get PUUID
            puuid = self.get_puuid(self.nick, self.tag)
            if not puuid:
                self.error.emit("Could not retrieve player PUUID. Check your Riot ID and API key.")
                return
                
            self.progress.emit(10)
            
            # Step 2: Get match IDs
            match_ids = self.get_match_ids(puuid, self.match_count)
            if not match_ids:
                self.error.emit("No matches found for this player.")
                return
                
            self.progress.emit(30)
            
            # Step 3: Get match details
            results = []
            for idx, match_id in enumerate(match_ids):
                match_data = self.get_match_details(puuid, match_id)
                if match_data:
                    results.append(match_data)
                progress = 30 + int((idx + 1) / len(match_ids) * 70)
                self.progress.emit(progress)
                
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"An error occurred: {str(e)}")
            
    def get_puuid(self, nick, tag):
        url = f"https://{self.region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{nick}/{tag}"
        headers = {"X-Riot-Token": self.api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()['puuid']
        else:
            print(f"Error retrieving PUUID: {response.status_code} - {response.text}")
            return None
            
    def get_match_ids(self, puuid, count=10):
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}"
        headers = {"X-Riot-Token": self.api_key}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error retrieving match IDs: {response.status_code} - {response.text}")
            return []
            
    def get_match_details(self, puuid, match_id):
        url = f"https://{self.region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        headers = {
            "X-Riot-Token": self.api_key,
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error retrieving match {match_id}: {response.status_code}")
            return None
            
        data = response.json()
        players = data["info"]["participants"]
        
        # Divide players into teams
        team1 = [p for p in players if p["teamId"] == 100]
        team2 = [p for p in players if p["teamId"] == 200]
        
        # Determine which team the player is on
        player_team = 1 if any(p["puuid"] == puuid for p in team1) else 2
        allied_team = team1 if player_team == 1 else team2
        enemy_team = team2 if player_team == 1 else team1
        
        # Get match time in minutes
        game_duration = data["info"]["gameDuration"] / 60  # Convert to minutes
        
        # Get game result for player
        player = next((p for p in players if p["puuid"] == puuid), None)
        win = player["win"] if player else False
        
        # Return structured match data
        return {
            "match_id": match_id,
            "duration": game_duration,
            "win": win,
            "game_mode": data["info"]["gameMode"],
            "queue_id": data["info"]["queueId"],
            "game_version": data["info"]["gameVersion"],
            "player": player,
            "allied_team": allied_team,
            "enemy_team": enemy_team
        }

class TeamAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("How Bad Is Your Team? - LoL Analyzer")
        self.setMinimumSize(1000, 700)
        
        # Set dark theme
        self.apply_dark_theme()
        
        # Main layout
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
        
        # Form layout
        form_layout = QHBoxLayout()
        
        # API Key input
        api_layout = QVBoxLayout()
        api_label = QLabel("Riot API Key:")
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter your Riot API Key")
        self.api_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_input)
        form_layout.addLayout(api_layout)
        
        # Summoner name input
        name_layout = QVBoxLayout()
        name_label = QLabel("Summoner Name:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your Riot ID (e.g. T1 sosa)")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        form_layout.addLayout(name_layout)
        
        # Tag input
        tag_layout = QVBoxLayout()
        tag_label = QLabel("Tag:")
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Tag (e.g. win)")
        tag_layout.addWidget(tag_label)
        tag_layout.addWidget(self.tag_input)
        form_layout.addLayout(tag_layout)
        
        # Region selection
        region_layout = QVBoxLayout()
        region_label = QLabel("Region:")
        self.region_combo = QComboBox()
        for region in REGIONS.keys():
            self.region_combo.addItem(region)
        region_layout.addWidget(region_label)
        region_layout.addWidget(self.region_combo)
        form_layout.addLayout(region_layout)
        
        # Match count selection
        count_layout = QVBoxLayout()
        count_label = QLabel("Number of Matches:")
        self.count_combo = QComboBox()
        for count in [5, 10, 15, 20]:
            self.count_combo.addItem(str(count))
        self.count_combo.setCurrentIndex(1)  # Default to 10
        count_layout.addWidget(count_label)
        count_layout.addWidget(self.count_combo)
        form_layout.addLayout(count_layout)
        
        # Analyze button
        button_layout = QVBoxLayout()
        button_label = QLabel("")
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
        button_layout.addWidget(button_label)
        button_layout.addWidget(self.analyze_button)
        form_layout.addLayout(button_layout)
        
        main_layout.addLayout(form_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Results area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Consolas", 10))
        self.results_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #DCDCDC;
                border: 1px solid #3F3F3F;
                padding: 5px;
            }
        """)
        main_layout.addWidget(self.results_text)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Worker thread
        self.worker = None
        
    def apply_dark_theme(self):
        dark_palette = QPalette()
        
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
        """)
        
    def start_analysis(self):
        # Get inputs
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
        self.results_text.clear()
        self.results_text.append("⏳ Starting analysis...\n")
        
        # Update UI state
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
        self.progress_bar.setValue(value)
        
    def show_error(self, message):
        self.results_text.append(f"❌ Error: {message}")
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Analysis failed")
        
    def display_results(self, matches):
        self.results_text.clear()
        
        if not matches:
            self.results_text.append("No matches found to analyze.")
            self.analyze_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.statusBar().showMessage("Ready")
            return
            
        # Get player name
        player_name = matches[0]["player"]["summonerName"]
        
        self.results_text.append(f"🏆 Analysis Results for {player_name}\n")
        self.results_text.append(f"📊 Analyzed {len(matches)} recent matches\n")
        
        # Calculate win rate
        wins = sum(1 for match in matches if match["win"])
        win_rate = (wins / len(matches)) * 100
        self.results_text.append(f"🎯 Win rate: {wins}/{len(matches)} ({win_rate:.1f}%)\n")
        
        # Calculate averages
        player_kdas = []
        team_kdas = []
        enemy_kdas = []
        
        for match in matches:
            player = match["player"]
            
            # Player stats
            player_kda = self.calculate_kda(player["kills"], player["deaths"], player["assists"])
            player_kdas.append(player_kda)
            
            # Team stats (excluding player)
            allies = [p for p in match["allied_team"] if p["puuid"] != player["puuid"]]
            for ally in allies:
                team_kda = self.calculate_kda(ally["kills"], ally["deaths"], ally["assists"])
                team_kdas.append(team_kda)
                
            # Enemy stats
            for enemy in match["enemy_team"]:
                enemy_kda = self.calculate_kda(enemy["kills"], enemy["deaths"], enemy["assists"])
                enemy_kdas.append(enemy_kda)
                
        # Calculate averages
        avg_player_kda = sum(player_kdas) / len(player_kdas) if player_kdas else 0
        avg_team_kda = sum(team_kdas) / len(team_kdas) if team_kdas else 0
        avg_enemy_kda = sum(enemy_kdas) / len(enemy_kdas) if enemy_kdas else 0
        
        self.results_text.append(f"💪 Your average KDA: {avg_player_kda:.2f}")
        self.results_text.append(f"👥 Your teammates' average KDA: {avg_team_kda:.2f}")
        self.results_text.append(f"👿 Enemy team average KDA: {avg_enemy_kda:.2f}\n")
        
        # Team quality assessment
        team_quality = avg_team_kda / avg_enemy_kda if avg_enemy_kda > 0 else 0
        
        self.results_text.append("🔍 Team Quality Assessment:")
        if team_quality >= 1.3:
            assessment = "AMAZING - You have exceptional teammates!"
        elif team_quality >= 1.1:
            assessment = "GOOD - Your teammates are performing well"
        elif team_quality >= 0.9:
            assessment = "AVERAGE - Your teammates are on par with enemies"
        elif team_quality >= 0.7:
            assessment = "BELOW AVERAGE - Your teammates are struggling a bit"
        else:
            assessment = "BAD - Your teammates are significantly underperforming"
            
        self.results_text.append(f"📝 {assessment} (Team performance ratio: {team_quality:.2f})\n")
        
        # Individual match analysis
        self.results_text.append("📋 Match Details:\n")
        
        for i, match in enumerate(matches):
            match_id = match["match_id"]
            game_mode = match["game_mode"]
            duration = match["duration"]
            result = "Victory" if match["win"] else "Defeat"
            
            self.results_text.append(f"🔸 Match {i+1}: {game_mode} - {result} ({duration:.1f} minutes)")
            
            # Player performance
            player = match["player"]
            player_kda = self.calculate_kda(player["kills"], player["deaths"], player["assists"])
            player_role = player.get("teamPosition", "Unknown")
            player_champion = player.get("championName", "Unknown")
            
            self.results_text.append(f"   You: {player_champion} ({player_role}) - {player['kills']}/{player['deaths']}/{player['assists']} (KDA: {player_kda:.2f})")
            
            # Team performance
            self.results_text.append("   🟢 Your Team:")
            allies = [p for p in match["allied_team"] if p["puuid"] != player["puuid"]]
            sorted_allies = self.sort_by_position(allies)
            
            for ally in sorted_allies:
                ally_kda = self.calculate_kda(ally["kills"], ally["deaths"], ally["assists"])
                ally_role = ally.get("teamPosition", "Unknown")
                ally_champion = ally.get("championName", "Unknown")
                self.results_text.append(f"   • {ally_champion} ({ally_role}): {ally['kills']}/{ally['deaths']}/{ally['assists']} (KDA: {ally_kda:.2f})")
                
            # Enemy performance
            self.results_text.append("   🔴 Enemy Team:")
            sorted_enemies = self.sort_by_position(match["enemy_team"])
            
            for enemy in sorted_enemies:
                enemy_kda = self.calculate_kda(enemy["kills"], enemy["deaths"], enemy["assists"])
                enemy_role = enemy.get("teamPosition", "Unknown")
                enemy_champion = enemy.get("championName", "Unknown")
                self.results_text.append(f"   • {enemy_champion} ({enemy_role}): {enemy['kills']}/{enemy['deaths']}/{enemy['assists']} (KDA: {enemy_kda:.2f})")
                
            self.results_text.append("")
            
        # Re-enable UI
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("Analysis complete")
        
    def calculate_kda(self, kills, deaths, assists):
        return (kills + assists) / max(1, deaths)
        
    def sort_by_position(self, players):
        position_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        return sorted(players, key=lambda x: position_order.index(x.get("teamPosition", "")) if x.get("teamPosition", "") in position_order else 99)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TeamAnalyzerApp()
    window.show()
    sys.exit(app.exec_())