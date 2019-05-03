#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
SumoManager

Manage different functions on the
RoboKoding SumoRobots.

Author: RoboKoding LTD
Website: https://www.robokoding.com
Contact: support@robokoding.com
"""

# python imports
import os
import sys
import json
import time
import string
import secrets
import argparse
import traceback
import urllib.request
import serial.tools.list_ports

# Local lib imports
from lib.esptool import *
from lib.files import Files
from lib.pyboard import Pyboard

# pyqt imports
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

# App versioning
APP_VERSION = '0.7.3'
APP_TIMESTAMP = '2019.05.01 22:20:00'

# App name
APP_NAME = 'SumoManager v' + APP_VERSION

# Ignore SSL
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Firmware URLs, file names
MICROPYTHON_URL = 'http://micropython.org/download'
FIRMWARE_FILE_NAMES = ['uwebsockets.py', 'config.json', 'hal.py', 'main.py', 'boot.py']
SUMOFIRMWARE_URL = 'https://raw.githubusercontent.com/robokoding/sumorobot-firmware/master/'

# Define the resource path
RESOURCE_PATH = 'res'
if hasattr(sys, '_MEIPASS'):
    RESOURCE_PATH = os.path.join(sys._MEIPASS, RESOURCE_PATH)

# Resource URLs
SUMO_IMG = os.path.join(RESOURCE_PATH, 'sumologo.svg')
USB_CON_IMG = os.path.join(RESOURCE_PATH, 'usb_con.png')
USB_DCON_IMG = os.path.join(RESOURCE_PATH, 'usb_dcon.png')
ORBITRON_FONT = os.path.join(RESOURCE_PATH, 'orbitron.ttf')

class SumoManager(QMainWindow):
    usb_dcon = pyqtSignal()
    usb_con = pyqtSignal(str)
    usb_list = pyqtSignal(list)
    message = pyqtSignal(str, str)
    dialog = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.initUI()

        self.config = None
        self.processing = None
        self.status_led_pin = 0
        self.connected_port = None

    def initUI(self):
        # Load the Orbitron font
        QFontDatabase.addApplicationFont(ORBITRON_FONT)

        # SumoRobot Logo
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(SUMO_IMG))
        logo_label.setAlignment(Qt.AlignCenter)

        # Serial port connection indication
        serial_label = QLabel('1. Connect SumoRobot via USB')
        serial_label.setStyleSheet('margin-top: 20px;')
        self.serial_image = QLabel()
        self.serial_image.setPixmap(QPixmap(USB_DCON_IMG))

        # WiFi credentials fields
        wifi_label = QLabel('2. Enter WiFi credentials')
        wifi_label.setStyleSheet('margin-top: 20px;')
        self.wifi_select = QComboBox()
        self.wifi_select.addItems(['Network name'])
        self.wifi_select.setEnabled(False)
        self.wifi_pwd_edit = QLineEdit()
        self.wifi_pwd_edit.setEchoMode(QLineEdit.Password)
        self.wifi_pwd_edit.setPlaceholderText("Password")

        # WiFi add button
        self.add_wifi_btn = QPushButton('Add WiFi network', self)
        self.add_wifi_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_wifi_btn.clicked.connect(self.button_clicked)
        self.wifi_pwd_edit.returnPressed.connect(self.button_clicked)

        # Add the statusbar into a toolbar
        self.tool_bar = self.addToolBar('Main')
        self.status_bar = QStatusBar()
        self.tool_bar.addWidget(self.status_bar)
        self.show_message('warning', 'Please connect your SumoRobot')

        # Vertical app layout
        vbox = QVBoxLayout()
        vbox.addWidget(logo_label)
        vbox.addWidget(serial_label)
        vbox.addWidget(self.serial_image)
        vbox.addWidget(wifi_label)
        vbox.addWidget(self.wifi_select)
        vbox.addWidget(self.wifi_pwd_edit)
        vbox.addWidget(self.add_wifi_btn)
        # Wrap the layout into a widget
        main_widget = QWidget()
        main_widget.setLayout(vbox)

        # Add menubar items
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        # Update robot ID menu item
        advanced_menu = QMenu('Advanced', self)
        file_menu.addMenu(advanced_menu)
        # Update robot ID menu item
        update_id = QAction('Update SumoID', self)
        update_id.triggered.connect(self.update_id)
        advanced_menu.addAction(update_id)
        # Show config menu item
        show_config = QAction('Show SumoConfig', self)
        show_config.triggered.connect(self.show_config)
        advanced_menu.addAction(show_config)
        # Update robot ID menu item
        update_id = QAction('Update SumoServer', self)
        update_id.triggered.connect(self.update_server)
        advanced_menu.addAction(update_id)
        # Update firmware menu item
        update_firmware = QAction('Update SumoFirmware', self)
        update_firmware.triggered.connect(self.update_firmware)
        file_menu.addAction(update_firmware)

        # Main window style, layout and position
        with open(os.path.join(RESOURCE_PATH, 'main.qss'), 'r') as file:
            self.setStyleSheet(file.read())
        self.setWindowTitle(APP_NAME)
        self.setCentralWidget(main_widget)
        self.show()
        self.center()
        # To lose focus on the textedit field
        self.setFocus()

    # Function to center the mainwindow on the screen
    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    @pyqtSlot(str, str)
    def show_message(self, type, message):
        if type == 'error':
            style = 'color: #d63634;'
        elif type == 'warning':
            style = 'color: #e77e34;'
        elif type == 'info':
            style = 'color: #1cc761;'
        else: # Unrecognized message type
            return

        self.status_bar.setStyleSheet(style)
        self.status_bar.showMessage(message)

    @pyqtSlot()
    @pyqtSlot(str)
    @pyqtSlot(list)
    def usb_action(self, data = None):
        if isinstance(data, list):
            self.wifi_select.clear()
            self.wifi_select.addItems(data)
            self.wifi_select.setEnabled(True)
            self.show_message('info', 'Successfully loaded WiFi networks')
            self.wifi_select.setStyleSheet('background-color: #2d3252;')
        elif isinstance(data, str):
            self.serial_image.setPixmap(QPixmap(USB_CON_IMG))
            self.show_message('warning', 'Loading WiFi networks...')
        else:
            self.connected_port = None
            self.serial_image.setPixmap(QPixmap(USB_DCON_IMG))
            self.show_message('warning', 'Please connect your SumoRobot')

    @pyqtSlot(str, str, str)
    def show_dialog(self, title, message, details):
        msg_box = QMessageBox()
        with open(os.path.join(RESOURCE_PATH, 'main.qss'), 'r') as file:
            msg_box.setStyleSheet(file.read())
        msg_box.setDetailedText(details)
        msg_box.setWindowTitle('Message')
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setStandardButtons(QMessageBox.Close)
        msg_box.setText(title)
        msg_box.setInformativeText('<font face=Arial>' + message + '</font>')
        horizontalSpacer = QSpacerItem(550, 0, QSizePolicy.Minimum, QSizePolicy.Expanding);
        layout = msg_box.layout();
        layout.addItem(horizontalSpacer, layout.rowCount(), 0, 1, layout.columnCount());
        msg_box.exec_()

    # When mouse clicked clear the focus on the input fields
    def mousePressEvent(self, event):
        # When the status bar is pressed
        self.wifi_pwd_edit.clearFocus()

    # Button clicked event
    def button_clicked(self):
        # When some thread is already processing SumoRobot is not connected
        if self.processing or not self.connected_port:
            return

        # When the network name is not valid
        if self.wifi_select.currentText() == 'Network name':
            # Show the error
            self.wifi_select.setStyleSheet('background-color: #d9534f;')
            return
        else: # When the network name is valid, remove the error
            self.wifi_select.setStyleSheet('background-color: #2d3252;')

        # To lose focus on the text edit field
        self.setFocus()
        # Indicates a background thread process
        self.processing = 'update_networks'

    def update_firmware(self, event):
        # When SumoRobot is connected and update config nor update firmware is running
        if self.connected_port and not self.processing:
            # Start the update firmware process
            self.processing = 'update_firmware'

    def show_config(self, event):
        if self.connected_port and not self.processing:
            self.show_dialog('SumoConfig',
                'Click Show Details... to see the SumoConfig contents',
                json.dumps(self.config, indent=8))

    def update_id(self, event):
        if self.connected_port and not self.processing:
            text, ok = QInputDialog.getText(self, 'SumoID',
                'Change SumoID:', QLineEdit.Normal, self.config['sumo_id'])
            if text and ok:
                self.config['sumo_id'] = text
                # Start the update ID process
                self.processing = 'update_id'

    def update_server(self, event):
        if self.connected_port and not self.processing:
            text, ok = QInputDialog.getText(self, 'SumoServer',
                'Change SumoServer:', QLineEdit.Normal, self.config['sumo_server'])
            if text and ok:
                self.config['sumo_server'] = text
                # Start the update server process
                self.processing = 'update_server'

class UpdateServer(QThread):
    def run(self):
        while True:
            # Wait until update server process is triggered
            if window.processing != 'update_server':
                time.sleep(1)
                continue

            window.message.emit('warning', 'Updating SumoServer...')
            try:
                # Open a connection
                board = Files(Pyboard(window.connected_port))
                # Save the new SumoServer
                temp = json.dumps(window.config, indent=8)
                board.put('config.json', temp)
                window.message.emit('info', 'Successfully updated SumoServer')
            except:
                window.dialog.emit('Error updating SumoServer',
                    '* Try reconnecting the SumoRobot USB cable<br>' +
                    '* Try updating SumoServer again', traceback.format_exc())
                window.message.emit('error', 'Error updating SumoServer')

            # Try to close the serial connection
            try:
                board.close()
            except:
                pass

            # Indicate that no process is running
            window.processing = None

class UpdateID(QThread):
    def run(self):
        while True:
            # Wait until update ID process is triggered
            if window.processing != 'update_id':
                time.sleep(1)
                continue

            window.message.emit('warning', 'Updating SumoID...')
            try:
                # Open a connection
                board = Files(Pyboard(window.connected_port))
                # Save the new SumoID
                temp = json.dumps(window.config, indent=8)
                board.put('config.json', temp)
                window.message.emit('info', 'Successfully updated SumoID')
                window.dialog.emit('New SumoID',
                    'Click Show Details... to see your new SumoID. Keep it secret and ' +
                    'change it when it has been exposed.', window.config['sumo_id'])
            except:
                window.dialog.emit('Error updating SumoID',
                    '* Try reconnecting the SumoRobot USB cable<br>' +
                    '* Try updating SumoID again', traceback.format_exc())
                window.message.emit('error', 'Error updating SumoID')

            # Try to close the serial connection
            try:
                board.close()
            except:
                pass

            # Indicate that no process is running
            window.processing = None

class UpdateFirmware(QThread):
    def run(self):
        while True:
            # Wait until update firmware process is triggered
            if window.processing != 'update_firmware':
                time.sleep(1)
                continue

            window.message.emit('warning', 'Updating SumoFirmware...')
            try:
                # Open and parse the MicroPython URL
                response = urllib.request.urlopen(MICROPYTHON_URL)
                line = response.readline()
                while line:
                    # Find the firmware binary URL
                    if b'firmware/esp32' in line:
                        firmware_url = line.split(b'"')[1].decode('utf-8')
                        break
                    line = response.readline()

                window.message.emit('warning', 'Downloading SumoFirmware... esp32.bin')
                # If not a complete URL
                if 'http' not in firmware_url:
                    # Complete the URL
                    firmware_url = MICROPYTHON_URL[:-9] + firmware_url
                # Open the parsed firmware binary URL
                response = urllib.request.urlopen(firmware_url)
                # Write the firmware binary into a local file
                temp_file = QTemporaryFile()
                temp_file.open()
                temp_file.writeData(response.read())
                temp_file.flush()

                # Firmware files to update
                data = dict.fromkeys(FIRMWARE_FILE_NAMES)

                # Download all firmware files
                for file_name in FIRMWARE_FILE_NAMES:
                    window.message.emit('warning', 'Downloading SumoFirmware... ' + file_name)
                    # Fetch the file from the Internet
                    response = urllib.request.urlopen(SUMOFIRMWARE_URL + file_name)
                    data[file_name] = response.read()

                # Detect the ESP version
                esp = ESPLoader.detect_chip(window.connected_port)

                # Check for ESP silicon features
                features = esp.get_chip_features()
                if ('VRef calibration in efuse' in features):
                    # Determine the status LED pin
                    window.status_led_pin = 5
                    print("main.py: UpdateFirmware() ESP features", features)

                # Erase the flash memory
                window.message.emit('warning', 'Erasing flash memory...')
                esp.run_stub()
                esp.IS_STUB = True
                esp.change_baud(460800)
                esp.STATUS_BYTES_LENGTH = 2
                erase_flash(esp, None)
                esp.flash_set_parameters(flash_size_bytes('4MB'))
                esp.FLASH_WRITE_SIZE = 0x4000
                esp.ESP_FLASH_DEFL_BEGIN = 0x10
                # Flash the latest MicroPython
                window.message.emit('warning', 'Flashing SumoFirmware... esp32.bin')
                write_flash(esp, argparse.Namespace(
                    addr_filename=[(4096, open(temp_file.fileName(), 'rb'))],
                    verify=False,
                    compress=None,
                    no_stub=False,
                    erase_all=False,
                    flash_mode='dio',
                    flash_size='4MB',
                    flash_freq='keep',
                    no_compress=False))
                esp.hard_reset()
                esp._port.close()

                # In case the user has a personalized config file
                if window.config:
                    # Transfer the personalized values
                    tmp_config = json.loads(data['config.json'])
                    tmp_config['wifis'] = window.config['wifis']
                    tmp_config['sumo_id'] = window.config['sumo_id']
                    tmp_config['status_led_pin'] = window.status_led_pin
                    tmp_config['sumo_server'] = window.config['sumo_server']
                    tmp_config['ultrasonic_distance'] = window.config['ultrasonic_distance']
                    tmp_config['left_line_value'] = window.config['left_line_value']
                    tmp_config['right_line_value'] = window.config['right_line_value']
                    tmp_config['left_line_threshold'] = window.config['left_line_threshold']
                    tmp_config['right_line_threshold'] = window.config['right_line_threshold']
                    data['config.json'] = json.dumps(tmp_config, indent=8)
                # In case it's the default config file
                else:
                    # Generate a random robot ID
                    random = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(8))
                    window.config = json.loads(data['config.json'])
                    window.config['sumo_id'] = random
                    window.config['status_led_pin'] = window.status_led_pin
                    data['config.json'] = json.dumps(window.config, indent=8)

                # Open the serial port
                board = Files(Pyboard(window.connected_port))

                # Go trough all the files
                for file_name in FIRMWARE_FILE_NAMES:
                    window.message.emit('warning', 'Flashing SumoFirmware... ' + file_name)
                    # Update file
                    board.put(file_name, data[file_name])

                window.message.emit('info', 'Successfully updated SumoFirmware')
                # Try to laod WiFi networks again
                window.connected_port = None
            except:
                window.dialog.emit('Error updating SumoFirmware',
                    '* Check your Internet connection<br>' +
                    '* Try reconnecting the SumoRobot USB cable<br>' +
                    '* Finally try File > Update SumoFirmware again',
                    traceback.format_exc())
                window.message.emit('error', 'Error updating SumoFirmware')

            # Try to close the serial connection
            try:
                board.close()
                esp._port.close()
            except:
                pass

            # Indicate that no process is running
            window.processing = None

class UpdateNetworks(QThread):
    def run(self):
        while True:
            # Wait until update networks process is triggered
            if window.processing != 'update_networks':
                time.sleep(1)
                continue

            window.message.emit('warning', 'Adding WiFi credentials...')
            try:
                # Open the serial port
                board = Files(Pyboard(window.connected_port))
                # Get the text from the input fields
                ssid = window.wifi_select.currentText()
                pwd = window.wifi_pwd_edit.text()
                # Add the WiFi credentials
                window.config['wifis'][ssid] = pwd
                # Convert the json object into a string
                temp = json.dumps(window.config, indent = 8)
                # Write the updates config file
                board.put('config.json', temp)
                window.message.emit('info', 'Successfully added WiFi credentials')
                window.dialog.emit('Successfully added WiFi credentials',
                    '<p>Now you can remove the USB cable. Wait for ' +
                    'the blue LED under the robot to be steady ON (means: SumoRobot is ' +
                    'successfully connected to the server). To see your SumoID ' +
                    'click Show Details... Keep in mind that other people can access your ' +
                    'SumoRobot with the SumoID. You can change it any time under ' +
                    'File > Advanced > Update SumoID. Now you can head' +
                    'over to the SumoInterface:</p>' +
                    '<a style="color:white;cursor:pointer;" href="http://sumo.robokoding.com">sumo.robokoding.com</a>' +
                    '<p>For further info about the SumoInterface head over to:</p>' +
                    '<a style="color:white;cursor:pointer;" href="https://wwww.robokoding.com/kits/sumorobot/sumointerface"' +
                    '>www.robokoding.com/kits/sumorobot/sumointerface</a>',
                    window.config['sumo_id'])
            except:
                window.dialog.emit('Error adding WiFi credentials',
                    '* Try adding WiFi credentials again<br>', +
                    '* Try reconnecting the SumoRobot USB cable<br>' +
                    '* Finally try File > Update SumoFirmware (close this dialog first)',
                    traceback.format_exc())
                window.message.emit('error', 'Error adding WiFi credentials')

            # Try to close the serial connection
            try:
                board.close()
            except:
                pass

            # Indicate that no process is running
            window.processing = None

class PortUpdate(QThread):
    # To update serialport status
    def run(self):
        while True:
            # Wait for a second to pass
            time.sleep(1)

            port = None
            hwid = None
            # Scan the serialports with specific vendor ID
            # TODO: implement with USB event
            for p in serial.tools.list_ports.comports():
                # When vendor ID was found
                if '1A86:' in p.hwid or '10C4:' in p.hwid:
                    hwid = p.hwid
                    port = p.device
                    break

            # When specific vendor ID was found and it's a new port
            if port and port != window.connected_port:
                # Different SumoRobot versions have a
                # different USB to UART IC hardware ID
                # Jiangsu Haoheng CH304 IC
                if '1A86:' in hwid:
                    window.status_led_pin = 22
                # Silicon Lab CP2104 IC
                elif '10C4:' in hwid:
                    window.status_led_pin = 5
                    print("PortUpdate: Detected SumoBoard v0.1.X")

                window.usb_con.emit(port)
                try:
                    board = None
                    # Initiate a serial connection
                    board = Files(Pyboard(port))
                    # Get the Wifi networks in range
                    networks, usb_charge = board.get_networks()
                    # Delay before next read
                    time.sleep(0.5)
                    # When the config file is present, load it
                    if any('config.json' in file for file in board.ls()):
                        print("PortUpdate: Loading SumoConfig (config.json) file")
                        window.config = json.loads(board.get('config.json'))
                    # Otherwise when no config file present, update the firmware
                    else:
                        print("PortUpdate: Sarting Update Firmware process")
                        window.processing = 'update_firmware'
                    # Emit a signal to populate networks
                    window.usb_list.emit(networks)
                except:
                    # If board had boot problems, reflash the SumoFirmware
                    if board and board._pyboard._data and b"flash read err" in board._pyboard._data:
                        print("PortUpdate: Boot problem, reflashing SumoFirmware")
                        window.processing = 'update_firmware'
                    # Otherwise show error as normal
                    else:
                        window.dialog.emit('Error loading WiFi networks',
                            '* Try reconnecting the SumoRobot USB cable<br>' +
                            '* When nothing helped try File > Update SumoFirmware (close this dialog first)',
                            traceback.format_exc())
                        window.message.emit('error', 'Error loading WiFi networks')

                # Try to close the serial connection
                try:
                    board.close()
                except:
                    pass

                window.connected_port = port
            # When no serial port with the specific vendor ID was found
            elif not port:
                window.usb_dcon.emit()

if __name__ == '__main__':
    # Initiate application
    app = QApplication(sys.argv)

    # For high dpi displays
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)

    # Create the app main window
    window = SumoManager()
    # Connect signals to slots
    window.dialog.connect(window.show_dialog)
    window.usb_con.connect(window.usb_action)
    window.usb_dcon.connect(window.usb_action)
    window.usb_list.connect(window.usb_action)
    window.message.connect(window.show_message)

    # Start port update thread
    port_update = PortUpdate()
    port_update.start()

    # Start the update config thread
    update_networks = UpdateNetworks()
    update_networks.start()

    # Start the update firmware thread
    update_firmware = UpdateFirmware()
    update_firmware.start()

    # Start update ID thread
    update_id = UpdateID()
    update_id.start()

    # Start update server thread
    update_server = UpdateServer()
    update_server.start()

    # Launch application
    sys.exit(app.exec_())
