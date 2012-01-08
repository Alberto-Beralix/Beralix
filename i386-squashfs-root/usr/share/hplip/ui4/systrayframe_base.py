# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui4/systrayframe_base.ui'
#
# Created: Mon May  4 14:30:37 2009
#      by: PyQt4 UI code generator 4.4.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(500, 540)
        self.gridlayout = QtGui.QGridLayout(Dialog)
        self.gridlayout.setObjectName("gridlayout")
        self.frame = QtGui.QFrame(Dialog)
        self.frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtGui.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.gridlayout1 = QtGui.QGridLayout(self.frame)
        self.gridlayout1.setObjectName("gridlayout1")
        self.groupBox_2 = QtGui.QGroupBox(self.frame)
        self.groupBox_2.setObjectName("groupBox_2")
        self.gridlayout2 = QtGui.QGridLayout(self.groupBox_2)
        self.gridlayout2.setObjectName("gridlayout2")
        self.radioButton = QtGui.QRadioButton(self.groupBox_2)
        self.radioButton.setObjectName("radioButton")
        self.gridlayout2.addWidget(self.radioButton, 0, 0, 1, 1)
        self.radioButton_2 = QtGui.QRadioButton(self.groupBox_2)
        self.radioButton_2.setObjectName("radioButton_2")
        self.gridlayout2.addWidget(self.radioButton_2, 1, 0, 1, 1)
        self.radioButton_3 = QtGui.QRadioButton(self.groupBox_2)
        self.radioButton_3.setObjectName("radioButton_3")
        self.gridlayout2.addWidget(self.radioButton_3, 2, 0, 1, 1)
        self.gridlayout1.addWidget(self.groupBox_2, 0, 0, 1, 1)
        self.groupBox_3 = QtGui.QGroupBox(self.frame)
        self.groupBox_3.setObjectName("groupBox_3")
        self.gridlayout3 = QtGui.QGridLayout(self.groupBox_3)
        self.gridlayout3.setObjectName("gridlayout3")
        self.label_2 = QtGui.QLabel(self.groupBox_3)
        self.label_2.setObjectName("label_2")
        self.gridlayout3.addWidget(self.label_2, 0, 0, 1, 1)
        self.MessageShowComboBox = QtGui.QComboBox(self.groupBox_3)
        self.MessageShowComboBox.setObjectName("MessageShowComboBox")
        self.gridlayout3.addWidget(self.MessageShowComboBox, 1, 0, 1, 1)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        self.gridlayout3.addItem(spacerItem, 2, 0, 1, 1)
        self.gridlayout1.addWidget(self.groupBox_3, 0, 1, 1, 1)
        self.groupBox = QtGui.QGroupBox(self.frame)
        self.groupBox.setCheckable(True)
        self.groupBox.setObjectName("groupBox")
        self.gridlayout4 = QtGui.QGridLayout(self.groupBox)
        self.gridlayout4.setObjectName("gridlayout4")
        self.label = QtGui.QLabel(self.groupBox)
        self.label.setObjectName("label")
        self.gridlayout4.addWidget(self.label, 0, 0, 1, 1)
        self.listWidget = QtGui.QListWidget(self.groupBox)
        self.listWidget.setObjectName("listWidget")
        self.gridlayout4.addWidget(self.listWidget, 1, 0, 1, 1)
        self.gridlayout1.addWidget(self.groupBox, 1, 0, 1, 2)
        self.gridlayout.addWidget(self.frame, 0, 0, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox_2.setTitle(QtGui.QApplication.translate("Dialog", "System tray icon visibility", None, QtGui.QApplication.UnicodeUTF8))
        self.radioButton.setText(QtGui.QApplication.translate("Dialog", "Always show", None, QtGui.QApplication.UnicodeUTF8))
        self.radioButton_2.setText(QtGui.QApplication.translate("Dialog", "Hide when inactive", None, QtGui.QApplication.UnicodeUTF8))
        self.radioButton_3.setText(QtGui.QApplication.translate("Dialog", "Always hide", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox_3.setTitle(QtGui.QApplication.translate("Dialog", "System tray icon messages", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Dialog", "Which messages to show:", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox.setTitle(QtGui.QApplication.translate("Dialog", "Monitor button presses on devices", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Dialog", "Devices to monitor:", None, QtGui.QApplication.UnicodeUTF8))

