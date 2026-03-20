#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nanopipette IV-Curve Fitter
Single-panel: left file browser | right IV plot + controls + results
Formula: D = (4/κ) × (1 / (R·π·tanθ))
"""

import os
import json
import numpy as np
from scipy import optimize

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QWidget, QSplitter,
    QMessageBox, QTextEdit, QCheckBox, QFormLayout,
    QDoubleSpinBox, QListWidget, QListWidgetItem,
    QLineEdit, QFileDialog, QApplication, QFrame,
    QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector

from core.data_processor import FileDataProcessor
from utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Pore size formula
# ---------------------------------------------------------------------------

def calculate_pore_diameter(R_GOhm: float,
                             kappa_Sm: float,
                             cone_half_angle_deg: float) -> float:
    """
    D = (4/κ) × (1 / (R·π·tanθ))
    R_GOhm   : resistance in GΩ  (= 1/G where G is in nS)
    kappa_Sm : solution conductivity in S/m
    cone_half_angle_deg: half cone angle in degrees
    With R in GΩ and κ in S/m the formula returns D directly in nm.
    """
    theta = np.radians(cone_half_angle_deg)
    return (4.0 / kappa_Sm) * (1.0 / (R_GOhm * np.pi * np.tan(theta)))


# ---------------------------------------------------------------------------
# Selectable value card
# ---------------------------------------------------------------------------

class ValueCard(QFrame):
    """Colour-coded card that shows a key result. Value text is selectable."""

    def __init__(self, label: str, unit: str, color: str = "#2c3e50", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 6px;
                border: none;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: rgba(255,255,255,0.70); font-size: 11px;")

        # Selectable value
        self._val = QLabel("—")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self._val.setStyleSheet("color: white; font-size: 20px;")
        self._val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._val.setCursor(QCursor(Qt.CursorShape.IBeamCursor))

        unit_lbl = QLabel(unit)
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit_lbl.setStyleSheet("color: rgba(255,255,255,0.60); font-size: 10px;")

        layout.addWidget(lbl)
        layout.addWidget(self._val)
        layout.addWidget(unit_lbl)

    def set_value(self, text: str):
        self._val.setText(text)

    def reset(self):
        self._val.setText("—")


# ---------------------------------------------------------------------------
# I-V canvas
# ---------------------------------------------------------------------------

class IVPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, on_region_selected=None):
        self.fig = Figure(figsize=(6, 4), dpi=100, tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self._fit_line = None
        self._span = None
        self._on_region_selected = on_region_selected
        self._init_axes()
        self.draw()

    def _init_axes(self):
        self.ax.set_xlabel("Voltage", fontsize=10)
        self.ax.set_ylabel("Current", fontsize=10)
        self.ax.grid(True, linestyle="--", alpha=0.45, color="#cccccc")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)

    def plot_iv(self, voltage, current, xlabel="Voltage (V)", ylabel="Current (nA)", title="I-V Curve"):
        self.ax.clear()
        self._fit_line = None
        order = np.argsort(voltage)
        self.ax.plot(voltage[order], current[order],
                     linewidth=1.0, color="#2980b9", alpha=0.9, label="Data")
        self.ax.set_xlabel(xlabel, fontsize=10)
        self.ax.set_ylabel(ylabel, fontsize=10)
        self.ax.set_title(title, fontsize=11, fontweight="bold", color="#2c3e50")
        self.ax.grid(True, linestyle="--", alpha=0.45, color="#cccccc")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.legend(fontsize=9)
        self.draw()
        self._install_span()

    def plot_fit(self, fit_v, fit_i):
        if self._fit_line is not None:
            try:
                self._fit_line.remove()
            except Exception:
                pass
        self._fit_line, = self.ax.plot(
            fit_v, fit_i, color="#e74c3c", linewidth=2.2,
            label="Linear Fit", zorder=5)
        handles, labels = self.ax.get_legend_handles_labels()
        seen, h2, l2 = set(), [], []
        for h, l in zip(handles, labels):
            if l not in seen:
                seen.add(l); h2.append(h); l2.append(l)
        self.ax.legend(h2, l2, fontsize=9)
        self.draw()

    def plot_multiple(self, curves_list, title="I-V Curve Comparison"):
        self.ax.clear()
        self._fit_line = None
        
        if len(curves_list) == 1:
            data_colors = ["#93a19d"] # RGB(147, 161, 157)
            fit_colors = ["#de6938"]  # RGB(222, 105, 56)
            data_alpha = 0.6
        else:
            colors = ["#2980b9", "#27ae60", "#e74c3c", "#8e44ad", "#e67e22", "#16a085", "#f39c12"]
            data_colors = colors
            fit_colors = colors
            # Use 0.01 representing 99% transparency
            data_alpha = 0.01
        
        for idx, curve in enumerate(curves_list):
            d_color = data_colors[idx % len(data_colors)]
            f_color = fit_colors[idx % len(fit_colors)]
            
            name = curve['name']
            data = curve['data']
            v_scale = data.get("v_scale", 1.0)
            i_scale = data.get("i_scale", 1.0)
            
            v = data["v_fit"] / v_scale
            i = data["i_fit"] / i_scale
            order = np.argsort(v)
            self.ax.plot(v[order], i[order], 
                         marker='o', markersize=3, linestyle='', 
                         alpha=data_alpha, color=d_color, 
                         markeredgecolor='none',
                         label=f"{name[:12]} Data")
            
            fit_v_V = np.linspace(data["v_fit"].min(), data["v_fit"].max(), 500)
            G_nS, offset_nA = data["popt"]
            fit_i_nA = G_nS * fit_v_V + offset_nA
            
            self.ax.plot(fit_v_V / v_scale, fit_i_nA / i_scale, 
                         color=f_color, linewidth=2.0, alpha=0.9,
                         label=f"{name[:12]} Fit")
                         
        if curves_list:
            v_unit = curves_list[0]['data']['v_unit']
            i_unit = curves_list[0]['data']['i_unit']
            self.ax.set_xlabel(f"Voltage ({v_unit})", fontsize=10)
            self.ax.set_ylabel(f"Current ({i_unit})", fontsize=10)
            
        self.ax.set_title(title, fontsize=11, fontweight="bold", color="#2c3e50")
        self.ax.grid(True, linestyle="--", alpha=0.45, color="#cccccc")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.legend(fontsize=8, loc='best')
        self.draw()

    def _install_span(self):
        if self._span is not None:
            try:
                self._span.set_visible(False)
            except Exception:
                pass
        if self._on_region_selected:
            self._span = SpanSelector(
                self.ax, self._on_region_selected, "horizontal",
                useblit=True,
                props=dict(alpha=0.20, facecolor="#f39c12"),
                interactive=True, drag_from_anywhere=True, minspan=1e-9)


# ---------------------------------------------------------------------------
# Data Canvas (Time/Index Series)
# ---------------------------------------------------------------------------

class DataPlotCanvas(FigureCanvas):
    def __init__(self, parent=None, on_region_selected=None):
        self.fig = Figure(figsize=(6, 5), dpi=100, tight_layout=True)
        self.ax_v = self.fig.add_subplot(211)
        self.ax_i = self.fig.add_subplot(212, sharex=self.ax_v)
        super().__init__(self.fig)
        self.setParent(parent)
        self._span = None
        self._on_region_selected = on_region_selected
        self._init_axes()
        self.draw()

    def _init_axes(self):
        for ax in (self.ax_v, self.ax_i):
            ax.grid(True, linestyle="--", alpha=0.45, color="#cccccc")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

    def plot_data(self, voltage, current, v_label="Voltage (V)", i_label="Current (nA)", title="Data"):
        self.ax_v.clear()
        self.ax_i.clear()
        self._init_axes()
        
        indices = np.arange(len(voltage))
        self.ax_v.plot(indices, voltage, color="#3498db", linewidth=1.0)
        self.ax_v.set_ylabel(v_label, fontsize=10)
        self.ax_v.set_title(title, fontsize=11, fontweight="bold", color="#2c3e50")
        
        self.ax_i.plot(indices, current, color="#e74c3c", linewidth=1.0)
        self.ax_i.set_ylabel(i_label, fontsize=10)
        self.ax_i.set_xlabel("Index", fontsize=10)

        self.draw()
        self._install_span()

    def _install_span(self):
        if self._span is not None:
            try:
                self._span.set_visible(False)
            except Exception:
                pass
        if self._on_region_selected:
            self._span = SpanSelector(
                self.ax_v, self._on_region_selected, "horizontal",
                useblit=True,
                props=dict(alpha=0.20, facecolor="#f39c12"),
                interactive=True, drag_from_anywhere=True, minspan=1)

# ---------------------------------------------------------------------------
# IV Result Dialog
# ---------------------------------------------------------------------------

class IVResultDialog(QDialog):
    def __init__(self, parent=None, default_dir=None):
        super().__init__(parent)
        self.setWindowTitle("I-V Curve Comparison & Results")
        self.resize(1100, 600)
        self.setModal(False)
        self._default_dir = default_dir or os.path.expanduser("~")
        
        self._preview_curve = None
        self._pinned_curves = []
        
        layout = QHBoxLayout(self)
        
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Saved Curves:"))
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.itemSelectionChanged.connect(self._replot_and_text)
        left_layout.addWidget(self._list)
        
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("Delete")
        btn_delete.setStyleSheet("background-color:#c0392b; color:white; font-weight:bold; padding:4px;")
        btn_delete.setToolTip("Delete selected curves")
        btn_delete.clicked.connect(self._delete_selected)
        btn_layout.addWidget(btn_delete)
        
        btn_export = QPushButton("Export")
        btn_export.setStyleSheet("background-color:#27ae60; color:white; font-weight:bold; padding:4px;")
        btn_export.setToolTip("Export selected curves data to CSV")
        btn_export.clicked.connect(self._export_data)
        btn_layout.addWidget(btn_export)
        
        left_layout.addLayout(btn_layout)
        
        layout.addLayout(left_layout, 2)
        
        center_layout = QVBoxLayout()
        self._canvas = IVPlotCanvas(self, on_region_selected=None)
        self._toolbar = NavigationToolbar(self._canvas, self)
        center_layout.addWidget(self._toolbar)
        center_layout.addWidget(self._canvas, 1)
        layout.addLayout(center_layout, 5)
        
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Fit Details:"))
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFont(QFont("Courier New", 10))
        right_layout.addWidget(self._detail)
        layout.addLayout(right_layout, 3)

    def set_preview(self, name, text, fit_data):
        self._preview_curve = {"name": f"[Preview] {name}", "text": text, "data": fit_data}
        self._replot_and_text()

    def add_curve(self, base_name, text, fit_data):
        idx = 1
        new_name = f"{base_name}_{idx}"
        existing_names = [c["name"] for c in self._pinned_curves]
        while new_name in existing_names:
            idx += 1
            new_name = f"{base_name}_{idx}"
            
        curve = {"name": new_name, "text": text, "data": fit_data}
        self._pinned_curves.append(curve)
        
        item = QListWidgetItem(new_name)
        item.setData(Qt.ItemDataRole.UserRole, curve)
        self._list.addItem(item)
        
        self._list.clearSelection()
        item.setSelected(True)
        
    def _replot_and_text(self):
        selected_items = self._list.selectedItems()
        selected_curves = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        curves_to_plot = []
        if self._preview_curve and not selected_curves:
            curves_to_plot = [self._preview_curve]
        else:
            curves_to_plot = selected_curves
            
        full_text = ""
        for c in curves_to_plot:
            full_text += f"==== {c['name']} ====\n" + c['text'] + "\n\n"
        self._detail.setPlainText(full_text)
        
        if hasattr(self._canvas, "plot_multiple"):
            self._canvas.plot_multiple(curves_to_plot)

    def _delete_selected(self):
        selected_items = self._list.selectedItems()
        if not selected_items:
            return
            
        for item in selected_items:
            curve = item.data(Qt.ItemDataRole.UserRole)
            if curve in self._pinned_curves:
                self._pinned_curves.remove(curve)
            row = self._list.row(item)
            self._list.takeItem(row)
            
        self._replot_and_text()

    def _export_data(self):
        selected_items = self._list.selectedItems()
        if not selected_items:
            if self._preview_curve and self._list.count() == 0:
                QMessageBox.information(self, "List Empty", "Please 'Pin' the curve first, then select it to export.")
            else:
                QMessageBox.information(self, "No Selection", "Please select at least one pinned curve from the list to export.")
            return
            
        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder", self._default_dir)
        if not folder: return
        
        for item in selected_items:
            curve = item.data(Qt.ItemDataRole.UserRole)
            name = curve["name"]
            data = curve["data"]
            fname = os.path.join(folder, f"{name}.csv")
            try:
                v = data["v_fit"]
                i = data["i_fit"]
                arr = np.column_stack((v, i))
                header = f"Voltage ({data['v_unit']}),Current ({data['i_unit']})"
                np.savetxt(fname, arr, delimiter=",", header=header, comments="")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Failed to export {name}:\n{e}")
                
        QMessageBox.information(self, "Export Complete", f"Exported {len(selected_items)} curves to {folder}")


# ---------------------------------------------------------------------------
# File browser
# ---------------------------------------------------------------------------

class FileBrowserPanel(QWidget):
    SUPPORTED_EXTS = {".tdms", ".h5", ".hdf5", ".abf", ".csv"}

    def __init__(self, parent=None, on_file_selected=None, initial_folder=None):
        super().__init__(parent)
        self._on_file_selected = on_file_selected
        self._current_folder = initial_folder or os.path.expanduser("~")
        self._nav_history = {}
        self._processor = FileDataProcessor()
        self._build_ui()
        self._load_folder(self._current_folder)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("File Browser")
        header.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        header.setStyleSheet(
            "color: #2c3e50; padding: 2px 2px 5px 2px;"
            "border-bottom: 1px solid #d0d7de;")
        layout.addWidget(header)

        path_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setMaximumWidth(60)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._folder_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._list = QListWidget()
        self._list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._list.itemClicked.connect(self._on_click)
        layout.addWidget(self._list, 1)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", self._current_folder)
        if folder:
            self._load_folder(folder)

    def _load_folder(self, path, highlight=None):
        self._current_folder = path
        self._folder_edit.setText(path)
        self._list.clear()
        parent = os.path.dirname(path)
        if parent != path:
            li = QListWidgetItem("..")
            li.setData(Qt.ItemDataRole.UserRole, parent)
            li.setForeground(li.foreground())
            self._list.addItem(li)
        if highlight is None:
            highlight = self._nav_history.get(path)
        try:
            dirs, files = [], []
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isdir(full):
                    dirs.append((name, full))
                elif os.path.splitext(name)[1].lower() in self.SUPPORTED_EXTS:
                    files.append((name, full))
            for name, fp in sorted(dirs, key=lambda x: x[0].lower()):
                li = QListWidgetItem(name + "/")
                li.setData(Qt.ItemDataRole.UserRole, fp)
                li.setToolTip(fp)
                self._list.addItem(li)
                if highlight and fp == highlight:
                    self._list.setCurrentItem(li)
            for name, fp in sorted(files, key=lambda x: x[0].lower()):
                li = QListWidgetItem(name)
                li.setData(Qt.ItemDataRole.UserRole, fp)
                li.setToolTip(fp)
                self._list.addItem(li)
                if highlight and fp == highlight:
                    self._list.setCurrentItem(li)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if os.path.isdir(path):
            if item.text() != "..":
                self._nav_history[self._current_folder] = path
            self._load_folder(path)
        elif os.path.isfile(path):
            if self._on_file_selected:
                self._on_file_selected(path, self._processor)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class SimpleFitterDialog(QDialog):
    """Nanopipette IV-Curve Fitter — single-panel, no tabs."""

    # unit -> scale factor to convert TO the working unit (V and nA)
    V_UNITS = {"V": 1.0, "mV": 1e-3}
    I_UNITS = {"nA": 1.0, "pA": 1e-3, "μA": 1e3}

    _SETTINGS_KEY = "fitter_settings"

    def __init__(self, parent=None, initial_folder=None):
        super().__init__(parent)
        self.setWindowTitle("Nanopipette IV-Curve Fitter")
        self.resize(1200, 760)

        self._raw_data = None
        self._voltage_data = None  # always stored in V
        self._current_data = None  # always stored in nA
        self._selected_vmin = None
        self._selected_vmax = None
        self._initial_folder = initial_folder
        self._current_folder = initial_folder or os.path.expanduser("~")
        self._config = ConfigManager()
        self._iv_dialog = None

        self._build_ui()
        self._load_settings()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left
        self._browser = FileBrowserPanel(
            parent=self,
            on_file_selected=self._on_file_selected,
            initial_folder=self._initial_folder)
        self._browser.setMinimumWidth(190)
        self._browser.setMaximumWidth(260)
        splitter.addWidget(self._browser)

        # Right
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 4, 4, 4)
        rl.setSpacing(5)

        rl.addWidget(self._build_channel_row())

        plot_group = QGroupBox("Voltage and Current Data")
        pg = QVBoxLayout(plot_group)
        pg.setContentsMargins(4, 8, 4, 4)
        self._canvas = DataPlotCanvas(parent=self, on_region_selected=self._on_span)
        self._toolbar = NavigationToolbar(self._canvas, self)
        self._toolbar.setMaximumHeight(30)
        pg.addWidget(self._toolbar)
        pg.addWidget(self._canvas, 1)
        rl.addWidget(plot_group, 4)

        rl.addWidget(self._build_fit_row())
        rl.addWidget(self._build_results_area(), 2)

        splitter.addWidget(right)
        splitter.setSizes([235, 965])
        root.addWidget(splitter)

    # ── Channel row ──────────────────────────────────────────────────

    def _build_channel_row(self):
        g = QGroupBox("Channel Selection")
        lay = QHBoxLayout(g)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Voltage:"))
        self._v_combo = QComboBox(); self._v_combo.setMinimumWidth(120)
        lay.addWidget(self._v_combo)
        self._v_unit = QComboBox()
        self._v_unit.addItems(list(self.V_UNITS.keys()))
        self._v_unit.setMaximumWidth(50)
        lay.addWidget(self._v_unit)

        lay.addWidget(QLabel("Current:"))
        self._i_combo = QComboBox(); self._i_combo.setMinimumWidth(120)
        lay.addWidget(self._i_combo)
        self._i_unit = QComboBox()
        self._i_unit.addItems(list(self.I_UNITS.keys()))
        self._i_unit.setMaximumWidth(55)
        lay.addWidget(self._i_unit)

        self._inv_v = QCheckBox("Invert V")
        self._inv_i = QCheckBox("Invert I")
        lay.addWidget(self._inv_v)
        lay.addWidget(self._inv_i)
        save_ch_btn = QPushButton("Save Channels")
        save_ch_btn.setStyleSheet("background-color:#7f8c8d; color:white; padding:4px 8px;")
        save_ch_btn.clicked.connect(self._save_channels)
        save_ch_btn.setToolTip("Save current Voltage/Current channel and invert settings as default.")
        lay.addWidget(save_ch_btn)

        lay.addStretch(1)

        self._v_combo.currentIndexChanged.connect(lambda _: self._auto_plot())
        self._i_combo.currentIndexChanged.connect(lambda _: self._auto_plot())
        self._v_unit.currentIndexChanged.connect(lambda _: self._auto_plot())
        self._i_unit.currentIndexChanged.connect(lambda _: self._auto_plot())
        self._inv_v.toggled.connect(lambda _: self._auto_plot())
        self._inv_i.toggled.connect(lambda _: self._auto_plot())

        return g

    # ── Fit controls ─────────────────────────────────────────────────

    def _build_fit_row(self):
        g = QGroupBox("Fit Controls")
        lay = QHBoxLayout(g)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Range:"))
        self._range_lbl = QLabel("Drag on the plot to select a fit region, or click Fit All")
        self._range_lbl.setStyleSheet("color: #95a5a6; font-style: italic;")
        lay.addWidget(self._range_lbl, 1)

        for text, color, use_sel in [
            ("Fit Selected Range", "#d35400", True),
            ("Fit All",            "#27ae60", False),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                f"background-color:{color}; color:white;"
                "font-weight:bold; padding:6px 14px;")
            btn.clicked.connect(
                (lambda s: lambda: self._perform_fit(s))(use_sel))
            lay.addWidget(btn)

        self._show_iv_btn = QPushButton("Show I-V Curve")
        self._show_iv_btn.setStyleSheet("background-color:#8e44ad; color:white; font-weight:bold; padding:6px 14px;")
        self._show_iv_btn.setEnabled(False)
        self._show_iv_btn.clicked.connect(self._show_iv_dialog)
        lay.addWidget(self._show_iv_btn)

        self._pin_btn = QPushButton("Pin to IV Curve")
        self._pin_btn.setStyleSheet("background-color:#f39c12; color:white; font-weight:bold; padding:6px 14px;")
        self._pin_btn.setEnabled(False)
        self._pin_btn.clicked.connect(self._pin_iv_curve)
        lay.addWidget(self._pin_btn)

        copy_btn = QPushButton("Copy")
        copy_btn.setMaximumWidth(65)
        copy_btn.clicked.connect(self._copy_results)
        lay.addWidget(copy_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setMaximumWidth(110)
        save_btn.setStyleSheet(
            "background-color:#7f8c8d; color:white; padding:6px 10px;")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setToolTip(
            "Save current channel selection, units, and nanopore parameters")
        lay.addWidget(save_btn)

        return g

    # ── Results area ─────────────────────────────────────────────────

    def _build_results_area(self):
        g = QGroupBox("Results")
        outer = QHBoxLayout(g)
        outer.setContentsMargins(8, 10, 8, 8)
        outer.setSpacing(15)

        # Key value cards
        cards = QHBoxLayout()
        cards.setSpacing(8)
        self._card_r   = ValueCard("Resistance",   "GΩ", "#2c3e50")
        self._card_g   = ValueCard("Conductance",  "nS", "#2471a3")
        self._card_d   = ValueCard("Pore Diameter","nm", "#148f77")
        for c in (self._card_r, self._card_g, self._card_d):
            c.setMinimumHeight(86)
            cards.addWidget(c)
        
        outer.addWidget(self._build_params(), 0)
        outer.addLayout(cards, 1)

        return g

    def _build_params(self):
        g = QGroupBox("Nanopore Parameters")
        g.setMaximumWidth(240)
        f = QFormLayout(g)
        f.setContentsMargins(8, 10, 8, 8)
        f.setSpacing(6)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._kappa = QDoubleSpinBox()
        self._kappa.setRange(0.001, 200)
        self._kappa.setValue(10.5)
        self._kappa.setDecimals(3)
        self._kappa.setSuffix(" S/m")
        f.addRow("Conductivity κ:", self._kappa)

        self._theta = QDoubleSpinBox()
        self._theta.setRange(0.1, 89.9)
        self._theta.setValue(5.0)
        self._theta.setDecimals(2)
        self._theta.setSuffix(" °")
        f.addRow("Half Cone Angle θ:", self._theta)

        note = QLabel(
            "<small><i>Formula:<br>"
            "D = (4/κ) (1/(R·π·tan θ))</i></small>")
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f8c8d; padding-top: 4px;")
        f.addRow(note)
        return g

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def set_data(self, data):
        """Called by main window on open."""
        self._raw_data = data
        self._populate_combos(data)
        self._auto_plot()

    def _populate_combos(self, data):
        self._v_combo.blockSignals(True)
        self._i_combo.blockSignals(True)
        self._v_combo.clear()
        self._i_combo.clear()
        if data is None:
            self._v_combo.blockSignals(False)
            self._i_combo.blockSignals(False)
            return
        channels = (list(data.keys()) if isinstance(data, dict)
                    else [f"Channel {i+1}"
                          for i in range(data.shape[1] if
                                         isinstance(data, np.ndarray) and
                                         data.ndim > 1 else 1)])
        self._v_combo.addItems(channels)
        self._i_combo.addItems(channels)
        if len(channels) >= 2:
            self._v_combo.setCurrentIndex(0)
            self._i_combo.setCurrentIndex(1)
        # Restore saved channel selections (must happen here, after channels
        # are populated — at _load_settings time the combos are still empty).
        s = self._config.config.get(self._SETTINGS_KEY, {})
        if s.get("v_channel") in channels:
            self._v_combo.setCurrentText(s["v_channel"])
        if s.get("i_channel") in channels:
            self._i_combo.setCurrentText(s["i_channel"])
            
        self._v_combo.blockSignals(False)
        self._i_combo.blockSignals(False)

    def _get_channel(self, data, combo):
        ch = combo.currentText()
        if isinstance(data, dict) and ch in data:
            return np.asarray(data[ch], dtype=float)
        if isinstance(data, np.ndarray):
            idx = int(ch.split(" ")[1]) - 1
            return (data[:, idx] if data.ndim > 1 else data).astype(float)
        return None

    def _on_file_selected(self, file_path, processor):
        ok, data, info = processor.load_file(file_path)
        if ok:
            self._raw_data = data
            self._current_folder = os.path.dirname(file_path)
            self._populate_combos(data)
            self._reset_results()
            self._auto_plot(title=os.path.basename(file_path))
        else:
            QMessageBox.warning(self, "Load Error",
                                info.get("Error", "Unknown error"))

    def _auto_plot(self, title=None):
        if self._raw_data is None:
            return
        if title is not None:
            self._current_title = title
        elif not hasattr(self, '_current_title'):
            self._current_title = "I-V Curve"

        v = self._get_channel(self._raw_data, self._v_combo)
        i = self._get_channel(self._raw_data, self._i_combo)
        if v is None or i is None:
            return

        if self._inv_v.isChecked(): v = -v
        if self._inv_i.isChecked(): i = -i

        # Apply unit scaling → always store V and nA internally
        v_scale = self.V_UNITS.get(self._v_unit.currentText(), 1.0)
        i_scale = self.I_UNITS.get(self._i_unit.currentText(), 1.0)
        v = v * v_scale  # convert to V
        i = i * i_scale  # convert to nA

        self._voltage_data = v
        self._current_data = i
        self._selected_vmin = self._selected_vmax = None
        self._range_lbl.setText("Drag on the plot to select a fit region, or click Fit All")
        self._range_lbl.setStyleSheet("color: #95a5a6; font-style: italic;")

        self._reset_results()

        v_lbl = f"Voltage ({self._v_unit.currentText()})"
        i_lbl = f"Current ({self._i_unit.currentText()})"
        self._canvas.plot_data(
            v / v_scale, i / i_scale,
            v_label=v_lbl, i_label=i_lbl,
            title=self._current_title)

    # ------------------------------------------------------------------
    # SpanSelector
    # ------------------------------------------------------------------

    def _on_span(self, imin, imax):
        if self._voltage_data is None:
            return
        idx_min = max(0, int(imin))
        idx_max = min(len(self._voltage_data)-1, int(imax))
        if idx_min >= idx_max:
             return
             
        self._selected_imin = idx_min
        self._selected_imax = idx_max
        self._range_lbl.setText(
            f"Index: [{idx_min} → {idx_max}]   "
            f"({idx_max - idx_min + 1} points)")
        self._range_lbl.setStyleSheet("color: #d35400; font-weight: bold;")

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def _perform_fit(self, use_selection: bool):
        if self._voltage_data is None:
            QMessageBox.warning(self, "No Data", "Load and plot a file first.")
            return

        v, i = self._voltage_data, self._current_data  # V and nA

        if use_selection:
            if getattr(self, '_selected_imin', None) is None:
                QMessageBox.information(
                    self, "No Selection",
                    "Drag on the Voltage plot to select a data region first.")
                return
            v_fit = v[self._selected_imin : self._selected_imax + 1]
            i_fit = i[self._selected_imin : self._selected_imax + 1]
            if len(v_fit) < 3:
                QMessageBox.warning(self, "Too Few Points",
                                    "Selected region has fewer than 3 points.")
                return
            region_str = f"Indices [{self._selected_imin} → {self._selected_imax}]"
        else:
            v_fit, i_fit = v, i
            region_str = "full range"

        try:
            popt, pcov = optimize.curve_fit(
                lambda x, g, b: g * x + b, v_fit, i_fit)
            G_nS, offset_nA = popt  # G in nS (I[nA]/V[V])
            G_err, b_err = np.sqrt(np.diag(pcov))

            i_pred = G_nS * v_fit + offset_nA
            residuals = i_fit - i_pred
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((i_fit - i_fit.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            rmse = np.sqrt((residuals ** 2).mean())

            # For the dialog we only need units
            v_scale = self.V_UNITS.get(self._v_unit.currentText(), 1.0)
            i_scale = self.I_UNITS.get(self._i_unit.currentText(), 1.0)

            # Key values
            R_GOhm = 1.0 / G_nS              # nS⁻¹ = GΩ

            kappa  = self._kappa.value()      # S/m
            theta  = self._theta.value()      # degrees

            # D = (4/κ) (1/(R·π·tanθ))  → nm when R in GΩ, κ in S/m
            D_nm = calculate_pore_diameter(R_GOhm, kappa, theta)

            # Update cards
            self._card_r.set_value(f"{R_GOhm:.4g}")
            self._card_g.set_value(f"{G_nS:.4g}")
            self._card_d.set_value(f"{D_nm:.2f}")

            # Detail text
            i_unit = self._i_unit.currentText()
            G_unit = f"nS  ({i_unit}/V)"
            b_unit = i_unit
            rmse_unit = i_unit

            det  = f"Linear Fit   I = G·V + b\n{'─'*42}\n"
            det += f"  Region    : {region_str}\n"
            det += f"  G         : {G_nS:.5g} ± {G_err:.2g} {G_unit}\n"
            det += f"  b         : {offset_nA/i_scale:.5g} ± {b_err/i_scale:.2g} {b_unit}\n"
            det += f"  R²        : {r2:.6f}\n"
            det += f"  RMSE      : {rmse/i_scale:.4g} {rmse_unit}\n"
            det += f"\nPore Size   D = (4/κ) (1/(R·π·tanθ))\n{'─'*42}\n"
            det += f"  R         : {R_GOhm:.4g} GΩ\n"
            det += f"  κ         : {kappa:.3f} S/m\n"
            det += f"  θ         : {theta:.2f}°\n"
            det += f"  Diameter  : {D_nm:.2f} nm\n"
            det += f"  Radius    : {D_nm/2:.2f} nm\n"

            self._last_result_text = det
            self._last_fit_data = {
                "v_fit": v_fit,
                "i_fit": i_fit,
                "popt": popt,
                "v_unit": self._v_unit.currentText(),
                "i_unit": self._i_unit.currentText(),
                "v_scale": v_scale,
                "i_scale": i_scale
            }
            if hasattr(self, '_show_iv_btn'):
                self._show_iv_btn.setEnabled(True)
                self._pin_btn.setEnabled(True)
                
            if self._iv_dialog is not None and self._iv_dialog.isVisible():
                title = getattr(self, '_current_title', "Data")
                self._iv_dialog.set_preview(title, self._last_result_text, self._last_fit_data)
            else:
                self._show_iv_dialog()

        except Exception as e:
            QMessageBox.critical(self, "Fit Error", str(e))

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _settings_dict(self) -> dict:
        return {
            "v_unit":       self._v_unit.currentText(),
            "i_unit":       self._i_unit.currentText(),
            "v_channel":    self._v_combo.currentText(),
            "i_channel":    self._i_combo.currentText(),
            "invert_v":     self._inv_v.isChecked(),
            "invert_i":     self._inv_i.isChecked(),
            "kappa":        self._kappa.value(),
            "theta":        self._theta.value(),
        }

    def _save_settings(self):
        self._config.update_config(self._SETTINGS_KEY, self._settings_dict())
        QMessageBox.information(
            self, "Settings Saved",
            "Current unit selections and nanopore parameters have been saved\n"
            "and will be restored next time you open the Fitter.")

    def _save_channels(self):
        self._config.update_config(self._SETTINGS_KEY, self._settings_dict())
        QMessageBox.information(self, "Channels Saved", "The default Voltage/Current channels and inverted states have been saved.")

    def _load_settings(self):
        s = self._config.config.get(self._SETTINGS_KEY)
        if not s:
            return
        if s.get("v_unit") in self.V_UNITS:
            self._v_unit.setCurrentText(s["v_unit"])
        if s.get("i_unit") in self.I_UNITS:
            self._i_unit.setCurrentText(s["i_unit"])
        if "kappa" in s:
            self._kappa.setValue(s["kappa"])
        if "theta" in s:
            self._theta.setValue(s["theta"])
        if "invert_v" in s:
            self._inv_v.setChecked(s["invert_v"])
        if "invert_i" in s:
            self._inv_i.setChecked(s["invert_i"])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_results(self):
        self._card_r.reset()
        self._card_g.reset()
        self._card_d.reset()
        self._last_result_text = ""
        self._last_fit_data = None
        if hasattr(self, '_show_iv_btn'):
            self._show_iv_btn.setEnabled(False)
            self._pin_btn.setEnabled(False)

    def _copy_results(self):
        if hasattr(self, '_last_result_text') and self._last_result_text:
            QApplication.clipboard().setText(self._last_result_text)
            QMessageBox.information(self, "Copied", "Results copied to clipboard.")
        else:
            QMessageBox.information(self, "Nothing to Copy", "Run a fit first.")

    def _show_iv_dialog(self):
        if not hasattr(self, '_last_fit_data') or not self._last_fit_data:
            return
            
        if self._iv_dialog is None:
            self._iv_dialog = IVResultDialog(self, default_dir=self._current_folder)
            
        title = getattr(self, '_current_title', "Data")
        self._iv_dialog.set_preview(title, self._last_result_text, self._last_fit_data)
        if not self._iv_dialog.isVisible():
            self._iv_dialog.show()

    def _pin_iv_curve(self):
        if not hasattr(self, '_last_fit_data') or not self._last_fit_data:
            return
            
        if self._iv_dialog is None:
            self._iv_dialog = IVResultDialog(self, default_dir=self._current_folder)
            
        title = getattr(self, '_current_title', "Data")
        base_name = os.path.splitext(title)[0]
        self._iv_dialog.add_curve(base_name, self._last_result_text, self._last_fit_data)
        if not self._iv_dialog.isVisible():
            self._iv_dialog.show()
