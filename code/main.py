import sys
import speech_recognition as sr
import pyaudio
import threading
from googletrans import Translator
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QComboBox, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QProgressBar, QGridLayout)
from PyQt6.QtGui import QPixmap, QFont, QIcon, QMouseEvent
from PyQt6.QtCore import Qt, QPoint
import json
from PIL import Image

# Configuration file path
CONFIG_FILE = "config.json"
CUSTOM_DICT_FILE = "custom_dict.json"
USER_FILE = "users.json"

# 사용자 정보 저장 및 로드
def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)

def load_users():
    try:
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

users = load_users()

def save_config(config):
    with open(CONFIG_FILE, 'w') as config_file:
        json.dump(config, config_file)

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        return {}

def load_custom_dict():
    try:
        with open(CUSTOM_DICT_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_custom_dict():
    with open(CUSTOM_DICT_FILE, 'w') as f:
        json.dump(custom_dict, f)

def get_default_microphone():
    p = pyaudio.PyAudio()
    default_device_index = p.get_default_input_device_info()["index"]
    p.terminate()
    return default_device_index

stop_listening = threading.Event()
last_active_time = time.time()
listener_thread = None
auto_stop_thread = None
custom_dict = load_custom_dict()

def center_window(window):
    frame_geometry = window.frameGeometry()
    screen_center = QApplication.primaryScreen().availableGeometry().center()
    frame_geometry.moveCenter(screen_center)
    window.move(frame_geometry.topLeft())

def center_child_window(parent, child):
    parent_rect = parent.geometry()
    parent_center = parent_rect.center()
    child_rect = child.frameGeometry()
    child_rect.moveCenter(parent_center)
    child.move(child_rect.topLeft())
    child.raise_()

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(parent.backgroundRole())
        self.setFixedHeight(40)
        self.parent = parent

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel("Live Translation", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.minimize_button = QPushButton("-", self)
        self.minimize_button.setFixedSize(40, 40)
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        self.maximize_button = QPushButton("⬜", self)
        self.maximize_button.setFixedSize(40, 40)
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)

        self.close_button = QPushButton("X", self)
        self.close_button.setFixedSize(40, 40)
        self.close_button.clicked.connect(self.parent.close)

        layout.addWidget(self.title_label)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

        self.setLayout(layout)
        self.apply_stylesheet()

    def apply_stylesheet(self):
        if self.parent.is_dark_theme:
            self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
            self.minimize_button.setStyleSheet("background-color: none; color: white;")
            self.maximize_button.setStyleSheet("background-color: none; color: white;")
            self.close_button.setStyleSheet("background-color: none; color: white;")
        else:
            self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
            self.minimize_button.setStyleSheet("background-color: none; color: black;")
            self.maximize_button.setStyleSheet("background-color: none; color: black;")
            self.close_button.setStyleSheet("background-color: none; color: black;")

    def toggle_maximize_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent.mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.parent.mouseMoveEvent(event)


class TranslatorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.lang_dict = {
            'English': 'en', '中文': 'zh-cn', '日本語': 'ja'}
        self.default_microphone_index = get_default_microphone()
        self.is_dark_theme = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        self.mouse_pos = None

        self.initUI()
        self.config = load_config()

    def initUI(self):
        self.setWindowTitle('Live Translation')
        self.setGeometry(100, 100, 380, 600)
        self.setWindowIcon(QIcon("icon.png"))

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # 로고 이미지 추가
        self.logo_label = QLabel(self)
        content_layout.addWidget(self.logo_label)
        
        self.apply_stylesheet()  # Apply stylesheet after defining logo_label

        # 로그인 프레임
        self.login_frame = QWidget()
        login_layout = QVBoxLayout()
        
        self.username_label = QLabel('아이디:', self)
        self.username_label.setFont(QFont('Helvetica', 14))
        login_layout.addWidget(self.username_label)
        
        self.username_entry = QLineEdit(self)
        login_layout.addWidget(self.username_entry)
        
        self.password_label = QLabel('비밀번호:', self)
        self.password_label.setFont(QFont('Helvetica', 14))
        login_layout.addWidget(self.password_label)
        
        self.password_entry = QLineEdit(self)
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        login_layout.addWidget(self.password_entry)
        
        self.login_button = QPushButton('로그인', self)
        self.login_button.clicked.connect(self.authenticate)
        login_layout.addWidget(self.login_button)
        
        self.register_button = QPushButton('회원가입', self)
        self.register_button.clicked.connect(self.register)
        self.register_button.setStyleSheet("background-color: #28a745; color: white;")
        login_layout.addWidget(self.register_button)
        
        self.login_frame.setLayout(login_layout)
        content_layout.addWidget(self.login_frame)
        
        # 번역 프레임
        self.translation_frame = QWidget()
        translation_layout = QVBoxLayout()

        button_layout = QGridLayout()

        self.start_button = QPushButton('시작', self)
        self.start_button.clicked.connect(self.start_listener)
        self.start_button.setStyleSheet("background-color: #007BFF; color: white;")
        button_layout.addWidget(self.start_button, 0, 0)
        
        self.stop_button = QPushButton('정지', self)
        self.stop_button.clicked.connect(self.stop_listener)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #dc3545; color: white;")
        button_layout.addWidget(self.stop_button, 0, 1)
        
        self.save_button = QPushButton('저장', self)
        self.save_button.clicked.connect(self.save_to_file)
        self.save_button.setStyleSheet("background-color: #17a2b8; color: white;")
        button_layout.addWidget(self.save_button, 0, 2)
        
        self.copy_button = QPushButton('복사', self)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setStyleSheet("background-color: #ffc107; color: white;")
        button_layout.addWidget(self.copy_button, 0, 3)
        
        self.clear_button = QPushButton('지우기', self)
        self.clear_button.clicked.connect(self.clear_texts)
        self.clear_button.setStyleSheet("background-color: #6c757d; color: white;")
        button_layout.addWidget(self.clear_button, 1, 0)
        
        self.theme_button = QPushButton('테마 변경', self)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.theme_button.setStyleSheet("background-color: #6610f2; color: white;")
        button_layout.addWidget(self.theme_button, 1, 1)
        
        self.lang_change_button = QPushButton('언어 변경', self)
        self.lang_change_button.clicked.connect(self.change_language)
        self.lang_change_button.setStyleSheet("background-color: #fd7e14; color: white;")
        button_layout.addWidget(self.lang_change_button, 1, 2)
        
        self.exit_button = QPushButton('종료', self)
        self.exit_button.clicked.connect(self.exit_app)
        self.exit_button.setStyleSheet("background-color: #343a40; color: white;")
        button_layout.addWidget(self.exit_button, 1, 3)

        translation_layout.addLayout(button_layout)
        
        self.text_widget_ko = QTextEdit(self)
        self.text_widget_ko.setReadOnly(True)
        translation_layout.addWidget(self.text_widget_ko)
        
        self.text_widget_translated = QTextEdit(self)
        self.text_widget_translated.setReadOnly(True)
        translation_layout.addWidget(self.text_widget_translated)
        
        self.status_label = QLabel(self)
        translation_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar(self)
        translation_layout.addWidget(self.progress_bar)
        
        self.translation_frame.setLayout(translation_layout)
        content_layout.addWidget(self.translation_frame)
        
        self.translation_frame.hide()

        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)
        
        center_window(self)

    def apply_stylesheet(self):
        stylesheet = """
            QWidget {
                background-color: #F5F5F5;
                font-family: 'Helvetica';
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                font-size: 14px;
            }
        """

        if self.is_dark_theme:
            stylesheet = """
                QWidget {
                    background-color: #2E2E2E;
                    font-family: 'Helvetica';
                }
                QLabel {
                    font-size: 14px;
                    color: #fff;
                }
                QLineEdit, QTextEdit {
                    background-color: #3E3E3E;
                    color: #fff;
                    border: 1px solid #555;
                    border-radius: 5px;
                    padding: 8px;
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #5A5A5A;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #777;
                }
                QProgressBar {
                    border: 1px solid #555;
                    border-radius: 5px;
                    text-align: center;
                    font-size: 14px;
                }
            """

        logo_path = "logo2.png" if self.is_dark_theme else "logo.png"
        self.setStyleSheet(stylesheet)
        self.update_logo(logo_path)

    def update_logo(self, logo_path):
        logo_image = Image.open(logo_path)
        logo_image = logo_image.resize((300, 100), Image.LANCZOS)
        logo_image.save("resized_logo.png")
        pixmap = QPixmap("resized_logo.png")
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def authenticate(self):
        username = self.username_entry.text()
        password = self.password_entry.text()

        if username in users and users[username] == password:
            self.show_language_selection()
        else:
            QMessageBox.critical(self, 'Error', '아이디와 비밀번호를 확인해주세요.')

    def show_language_selection(self):
        self.lang_window = LanguageSelectionPopup(self)
        self.lang_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.lang_window.show()
        self.lang_window.move(40, 150)

    def start_translation_frame(self):
        self.setGeometry(100, 100, 800, 600)
        self.translation_frame.show()
        self.login_frame.hide()
        if self.lang_window:
            self.lang_window.close()
        center_window(self)

    def register(self):
        self.reg_window = RegisterWindow(self)
        self.reg_window.setGeometry(100, 100, 400, 300)
        self.reg_window.move(40, 150)  # Adjust the position to top-left corner
        self.reg_window.show()

    def start_listener(self):
        global listener_thread, auto_stop_thread

        stop_listening.clear()
        last_active_time = time.time()
        selected_index = self.default_microphone_index
        selected_lang = self.lang_dict[self.lang_option.currentText()]

        listener_thread = threading.Thread(target=transcribe_from_microphone, args=(selected_index, selected_lang))
        auto_stop_thread = threading.Thread(target=self.auto_stop_listener)

        listener_thread.start()
        auto_stop_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_listener(self):
        global listener_thread, auto_stop_thread

        stop_listening.set()

        if listener_thread:
            listener_thread.join(timeout=1)
            listener_thread = None

        if auto_stop_thread:
            auto_stop_thread.join(timeout=1)
            auto_stop_thread = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("")

    def auto_stop_listener(self, timeout=300):
        global last_active_time
        while not stop_listening.is_set():
            if time.time() - last_active_time > timeout:
                self.status_label.setText(f"Auto stopping after {timeout} seconds of inactivity.")
                stop_listening.set()
            time.sleep(0.5)
    
    def save_to_file(self):
        file_content = f"Korean Subtitles:\n{self.text_widget_ko.toPlainText()}\n\nTranslated Subtitles:\n{self.text_widget_translated.toPlainText()}"
        file_path, _ = QFileDialog.getSaveFileName(self, 'Save File', '', 'Text files (*.txt);;All files (*.*)')
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(file_content)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_widget_translated.toPlainText().strip())
        QMessageBox.information(self, 'Copied to Clipboard', 'Translated subtitles have been copied to clipboard.')

    def clear_texts(self):
        self.text_widget_ko.clear()
        self.text_widget_translated.clear()

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.apply_stylesheet()
        self.title_bar.apply_stylesheet()  # 상단바의 스타일시트도 변경

    def change_language(self):
        if self.stop_button.isEnabled():
            QMessageBox.warning(self, '경고', '실행을 정지하시고 언어변경 버튼을 눌러주세요.')
        else:
            self.lang_window = LanguageSelectionPopup(self)
            self.lang_window.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.lang_window.show()
            self.lang_window.closeEvent = self.on_language_window_close

    def on_language_window_close(self, event):
        # 언어 창이 닫힐 때 번역창 크기를 800x600으로 고정
        self.setFixedSize(800, 600)
        event.accept()

    def start_translation_frame(self):
        self.setFixedSize(800, 600)  # 번역 창 크기 고정
        self.translation_frame.show()
        self.login_frame.hide()
        if self.lang_window:
            self.lang_window.close()
        center_window(self)

    def exit_app(self):
        self.stop_listener()
        save_config({'language': self.lang_option.currentText()})
        self.close()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.mouse_pos)
            event.accept()

class LanguageSelectionPopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        self.setWindowTitle('언어 선택')
        self.setGeometry(100, 100, 300, 200)

        layout = QVBoxLayout()

        self.lang_label = QLabel('언어를 선택하세요:', self)
        self.lang_label.setFont(QFont('Helvetica', 14))
        layout.addWidget(self.lang_label)

        self.lang_option = QComboBox(self)
        for lang in self.parent.lang_dict.keys():
            self.lang_option.addItem(lang)
        layout.addWidget(self.lang_option)

        self.ok_button = QPushButton('OK', self)
        self.ok_button.clicked.connect(self.set_language)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def set_language(self):
        self.parent.lang_option = self.lang_option
        self.parent.status_label.setText(f"Translation language set to {self.lang_option.currentText()}.")
        self.parent.start_translation_frame()
        self.close()

    def showEvent(self, event):
        # Adjust the window position
        self.move(250, 250)  # 위치 변경
        super().showEvent(event)

class RegisterWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('회원가입')
        self.setGeometry(100, 100, 400, 300)
        
        # 스타일시트 추가
        self.setStyleSheet("background-color: #f0f0f0;")  # 약간 회색빛 추가

        layout = QVBoxLayout()

        # 닫기 버튼을 우측 상단에 위치하게 설정
        close_button_layout = QHBoxLayout()
        self.close_button = QPushButton("X", self)
        self.close_button.setFixedSize(40, 40)
        self.close_button.clicked.connect(self.close)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
        """)
        close_button_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)
        close_button_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addLayout(close_button_layout)

        self.reg_username_label = QLabel('새 아이디:', self)
        self.reg_username_label.setFont(QFont('Helvetica', 14))
        layout.addWidget(self.reg_username_label)

        self.reg_username_entry = QLineEdit(self)
        layout.addWidget(self.reg_username_entry)

        self.reg_password_label = QLabel('새 비밀번호:', self)
        self.reg_password_label.setFont(QFont('Helvetica', 14))
        layout.addWidget(self.reg_password_label)

        self.reg_password_entry = QLineEdit(self)
        self.reg_password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.reg_password_entry)

        # 버튼 레이아웃 추가
        button_layout = QHBoxLayout()
        self.register_button = QPushButton('등록', self)
        self.register_button.clicked.connect(self.save_registration)
        self.register_button.setStyleSheet("background-color: #28a745; color: white;")  # 로그인 버튼과 동일한 스타일 적용
        button_layout.addWidget(self.register_button)

        self.confirm_button = QPushButton('확인', self)
        self.confirm_button.clicked.connect(self.close)
        button_layout.addWidget(self.confirm_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_registration(self):
        reg_username = self.reg_username_entry.text()
        reg_password = self.reg_password_entry.text()

        if reg_username and reg_password:
            if reg_username in users:
                QMessageBox.critical(self, 'Error', '동일한 아이디가 존재합니다.')
            else:
                users[reg_username] = reg_password
                save_users(users)
                QMessageBox.information(self, 'Success', '회원가입이 완료되었습니다!')
                self.close()
        else:
            QMessageBox.critical(self, 'Error', '아이디와 비밀번호를 확인해주세요.')

    def showEvent(self, event):
        # Adjust the window position to the top-left corner
        self.move(0, 150)  # Adjust the position to top-left corner
        self.raise_()  # Bring the window to the front
        super().showEvent(event)


def transcribe_from_microphone(device_index, lang):
    global last_active_time
    recognizer = sr.Recognizer()
    microphone = sr.Microphone(device_index=device_index)
    translator = Translator()

    with microphone as source:
        ex.status_label.setText("주변 소음 조정 중... 잠시 기다려주세요.")
        recognizer.adjust_for_ambient_noise(source)
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.5
        recognizer.phrase_time_limit = None

        ex.status_label.setText("녹음 준비 완료. 말하기 시작하세요...")

        while not stop_listening.is_set():
            ex.status_label.setText("듣고 있습니다...")
            ex.progress_bar.setRange(0, 0)
            try:
                audio_data = recognizer.listen(source, timeout=10)
                ex.status_label.setText("처리 중...")

                threading.Thread(target=process_audio, args=(recognizer, audio_data, lang)).start()
                
                time.sleep(0.5)

            except sr.WaitTimeoutError:
                ex.status_label.setText("제한 시간 내에 말소리를 감지하지 못했습니다.")
            except sr.UnknownValueError:
                ex.status_label.setText("음성을 이해하지 못했습니다.")
            except sr.RequestError as e:
                ex.status_label.setText(f"구글 음성 인식 서비스에 요청할 수 없습니다; {e}")
            except Exception as e:
                ex.status_label.setText(f"번역 중 오류가 발생했습니다: {e}")
            finally:
                ex.progress_bar.setRange(0, 1)

def process_audio(recognizer, audio_data, lang):
    global last_active_time
    translator = Translator()
    try:
        start_recognition_time = time.time()  # 음성 인식 시작 시간
        text_ko = recognizer.recognize_google(audio_data, language='ko-KR')
        recognition_end_time = time.time()  # 음성 인식 완료 시간
        last_active_time = time.time()

        for term, translation in custom_dict.items():
            text_ko = text_ko.replace(term, translation)

        text_ko = preprocess_text(text_ko)
        
        translated_text = translator.translate(text_ko, src='ko', dest=lang).text

        translated_text = postprocess_text(translated_text)

        ex.status_label.setText("번역 완료")

        recognition_time = recognition_end_time - start_recognition_time

        time_info = f"(인식 시간: {recognition_time:.2f}s)"
        
        update_text_widgets(text_ko, translated_text, lang, time_info)

    except sr.UnknownValueError:
        ex.status_label.setText("음성을 이해하지 못했습니다.")
    except sr.RequestError as e:
        ex.status_label.setText(f"구글 음성 인식 서비스에 요청할 수 없습니다; {e}")
    except Exception as e:
        ex.status_label.setText(f"번역 중 오류가 발생했습니다: {e}")

def preprocess_text(text):
    return text

def postprocess_text(text):
    return text

def update_text_widgets(text_ko, translated_text, lang, time_info):
    ex.text_widget_ko.append(f"{text_ko}\n")
    ex.text_widget_translated.append(f"{translated_text} {time_info}\n")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TranslatorApp()
    ex.show()

    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Closing Window...")