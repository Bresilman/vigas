import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QPushButton, QLabel, QFileDialog, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QListWidget, QGroupBox, QSpinBox, QSplitter, QCheckBox, QTextEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont

# Integração Matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from app.controllers.beam_controller import BeamController
from app.models.entities import LoadType

# --- CANVAS PARA DIAGRAMAS (Aba 2) ---
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes_shear = self.fig.add_subplot(211)
        self.axes_moment = self.fig.add_subplot(212, sharex=self.axes_shear)
        self.fig.tight_layout(pad=3.0)
        super(MplCanvas, self).__init__(self.fig)

# --- CANVAS PARA PLANTA DE FORMA (Aba 1 - Novo!) ---
class StructuralViewCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_aspect('equal')
        self.fig.tight_layout(pad=2.0)
        super(StructuralViewCanvas, self).__init__(self.fig)

    def plot_structure(self, beams_dict):
        self.ax.cla()
        
        for b_id, beam in beams_dict.items():
            if not beam.nodes: continue
            
            x_coords = [n.x for n in beam.nodes]
            y_coords = [n.y for n in beam.nodes]
            
            self.ax.plot(x_coords, y_coords, 'o-', linewidth=3, markersize=8, label=b_id, color='#2c3e50')
            
            mid_x = np.mean(x_coords)
            mid_y = np.mean(y_coords)
            self.ax.text(mid_x, mid_y, b_id, fontsize=10, fontweight='bold', 
                         color='white', bbox=dict(facecolor='red', alpha=0.7, edgecolor='none'))
            
            for node in beam.nodes:
                if node.support_conditions[0]: 
                    self.ax.plot(node.x, node.y, '^', color='black', markersize=10)

        self.ax.set_title("Planta de Forma (Esquemática)")
        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.grid(True, linestyle='--', alpha=0.4)
        self.draw()

# --- JANELA PRINCIPAL ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("PyViga 2026 - Sistema Integrado de Vigas")
        self.setGeometry(50, 50, 1400, 900)
        
        self.controller = BeamController()
        self.current_beams = {} 
        self.selected_beam_id = None
        self.pillar_data_cache = [] # Armazena dados dos pilares para exportação

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self._create_menu_bar()

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # ABA 1: Visão Geral (Tabela + Planta 2D)
        self.tab_project = QWidget()
        self._setup_tab_project()
        self.tabs.addTab(self.tab_project, "📁 Visão Geral & Planta")
        
        # ABA 2: O Editor
        self.tab_design = QWidget()
        self._setup_tab_design()
        self.tabs.addTab(self.tab_design, "📐 Editor de Vigas")
        
        # ABA 3: Exportação (Editor de Pilares)
        self.tab_reports = QWidget()
        self._setup_tab_reports()
        self.tabs.addTab(self.tab_reports, "🏗️ Pilares & Exportação")

        self.statusBar().showMessage("Pronto.")

    def _create_menu_bar(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("Arquivo")
        action_import = QAction("Importar JSON...", self)
        action_import.triggered.connect(self._import_json)
        file_menu.addAction(action_import)
        
        action_exit = QAction("Sair", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _setup_tab_project(self):
        layout = QHBoxLayout(self.tab_project)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Painel Esquerdo
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        btn_layout = QHBoxLayout()
        self.btn_import = QPushButton("Importar Lajes (vigas.json)")
        self.btn_import.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        self.btn_import.clicked.connect(self._import_json)
        btn_layout.addWidget(self.btn_import)
        left_layout.addLayout(btn_layout)
        
        self.table_beams = QTableWidget()
        self.table_beams.setColumnCount(5)
        self.table_beams.setHorizontalHeaderLabels(["ID", "Seção", "Comp. (m)", "Carga Total", "Status"])
        self.table_beams.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.table_beams)
        
        left_panel.setLayout(left_layout)
        
        # Painel Direito
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("<b>Visualização da Planta Estrutural:</b>"))
        
        self.structure_canvas = StructuralViewCanvas(self, width=5, height=5, dpi=100)
        right_layout.addWidget(self.structure_canvas)
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 700])
        
        layout.addWidget(splitter)

    def _setup_tab_design(self):
        layout = QHBoxLayout(self.tab_design)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Esquerda
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("<b>Selecione a Viga:</b>"))
        self.list_beams = QListWidget()
        self.list_beams.itemClicked.connect(self._on_beam_selected)
        left_layout.addWidget(self.list_beams)
        left_panel.setLayout(left_layout)
        
        # Direita
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Gráficos
        self.canvas = MplCanvas(self, width=5, height=5, dpi=100)
        right_layout.addWidget(self.canvas, stretch=2)
        
        # Ferramentas
        self.group_edit = QGroupBox("Propriedades da Viga (Edição Manual)")
        self.group_edit.setEnabled(False)
        edit_layout = QHBoxLayout()
        
        edit_layout.addWidget(QLabel("Bw (cm):"))
        self.spin_bw = QSpinBox()
        self.spin_bw.setRange(10, 100); self.spin_bw.setValue(15)
        edit_layout.addWidget(self.spin_bw)
        
        edit_layout.addWidget(QLabel("H (cm):"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(20, 200); self.spin_h.setValue(40)
        edit_layout.addWidget(self.spin_h)
        
        self.chk_fix_start = QCheckBox("Engastar Início")
        self.chk_fix_end = QCheckBox("Engastar Fim")
        edit_layout.addWidget(self.chk_fix_start)
        edit_layout.addWidget(self.chk_fix_end)
        
        self.btn_recalc = QPushButton("🔄 Atualizar")
        self.btn_recalc.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.btn_recalc.clicked.connect(self._manual_update)
        edit_layout.addWidget(self.btn_recalc)
        
        self.btn_optimize = QPushButton("🚀 Otimizar Altura")
        self.btn_optimize.clicked.connect(self._run_optimization_gui)
        edit_layout.addWidget(self.btn_optimize)
        
        self.group_edit.setLayout(edit_layout)
        right_layout.addWidget(self.group_edit)
        
        # Detalhes
        right_layout.addWidget(QLabel("<b>Resultados Detalhados:</b>"))
        self.table_detail = QTableWidget()
        self.table_detail.setColumnCount(4)
        self.table_detail.setHorizontalHeaderLabels(["Posição", "Armadura", "Área (cm²)", "Status"])
        self.table_detail.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.table_detail, stretch=1)
        
        right_panel.setLayout(right_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 900])
        layout.addWidget(splitter)

    def _setup_tab_reports(self):
        layout = QVBoxLayout(self.tab_reports)
        
        # Cabeçalho
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Gestão de Cargas nos Pilares</b> (Edite os nomes antes de exportar)"))
        
        self.btn_calc_pillars = QPushButton("🔄 Calcular Reações e Carregar Tabela")
        self.btn_calc_pillars.clicked.connect(self._load_pillar_table)
        header.addWidget(self.btn_calc_pillars)
        layout.addLayout(header)
        
        # Tabela de Pilares
        self.table_pillars = QTableWidget()
        self.table_pillars.setColumnCount(6)
        self.table_pillars.setHorizontalHeaderLabels(["ID Pilar (Editável)", "Coord (X,Y)", "Fz (kN)", "Mx (kNm)", "My (kNm)", "Origem"])
        self.table_pillars.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_pillars)
        
        # Botões Rodapé
        footer = QHBoxLayout()
        
        self.btn_save_json = QPushButton("💾 Exportar JSON (PyPilar)")
        self.btn_save_json.setMinimumHeight(40)
        self.btn_save_json.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_save_json.clicked.connect(self._export_pillars_json)
        footer.addWidget(self.btn_save_json)
        
        self.btn_gen_mem = QPushButton("📝 Gerar Memorial Descritivo (.md)")
        self.btn_gen_mem.setMinimumHeight(40)
        self.btn_gen_mem.clicked.connect(self._save_memorial_file)
        footer.addWidget(self.btn_gen_mem)
        
        layout.addLayout(footer)

    # --- LÓGICA DO SISTEMA ---

    def _import_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir JSON", "", "JSON (*.json)")
        if file_path:
            try:
                self.current_beams = self.controller.run_batch_analysis(file_path)
                self._update_ui_after_import()
                self.structure_canvas.plot_structure(self.current_beams)
                
                if self.list_beams.count() > 0:
                    self.list_beams.setCurrentRow(0)
                    self._on_beam_selected(self.list_beams.item(0))
                
                self.statusBar().showMessage(f"Importado: {len(self.current_beams)} vigas.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def _update_ui_after_import(self):
        # Aba 1
        self.table_beams.setRowCount(0)
        for row, (b_id, beam) in enumerate(self.current_beams.items()):
            self.table_beams.insertRow(row)
            self.table_beams.setItem(row, 0, QTableWidgetItem(b_id))
            
            sec = f"{beam.spans[0].section.bw}x{beam.spans[0].section.h}"
            self.table_beams.setItem(row, 1, QTableWidgetItem(sec))
            
            comp = sum(s.length for s in beam.spans)
            self.table_beams.setItem(row, 2, QTableWidgetItem(f"{comp:.2f}"))
            
            try:
                total_load = 0
                for span in beam.spans:
                    q = sum(l.value for l in span.loads if l.load_type == LoadType.DISTRIBUTED)
                    total_load += q * span.length
                self.table_beams.setItem(row, 3, QTableWidgetItem(f"{total_load:.1f}"))
            except:
                 self.table_beams.setItem(row, 3, QTableWidgetItem("-"))

            self.table_beams.setItem(row, 4, QTableWidgetItem("Calculado"))

        # Aba 2
        self.list_beams.clear()
        for b_id in self.current_beams.keys():
            self.list_beams.addItem(b_id)

    def _on_beam_selected(self, item):
        if not item: return
        self.selected_beam_id = item.text()
        beam = self.current_beams[self.selected_beam_id]
        
        first_span = beam.spans[0]
        self.spin_bw.setValue(int(first_span.section.bw))
        self.spin_h.setValue(int(first_span.section.h))
        
        node_start = beam.nodes[0]
        node_end = beam.nodes[-1]
        self.chk_fix_start.setChecked(node_start.support_conditions[1])
        self.chk_fix_end.setChecked(node_end.support_conditions[1])
        
        self.group_edit.setEnabled(True)
        self._refresh_visualization(beam)

    def _manual_update(self):
        if not self.selected_beam_id: return
        beam = self.current_beams[self.selected_beam_id]
        
        new_bw = self.spin_bw.value()
        new_h = self.spin_h.value()
        is_fixed_start = self.chk_fix_start.isChecked()
        is_fixed_end = self.chk_fix_end.isChecked()
        
        for span in beam.spans:
            span.section.bw = float(new_bw)
            span.section.h = float(new_h)
            for load in span.loads:
                if load.source == "Peso Próprio":
                    load.value = (new_bw/100) * (new_h/100) * 25.0
        
        beam.nodes[0].support_conditions[1] = is_fixed_start
        beam.nodes[-1].support_conditions[1] = is_fixed_end
        
        try:
            self.controller._process_single_beam(beam)
            self._refresh_visualization(beam)
            self._update_ui_after_import()
            self.statusBar().showMessage(f"Viga {beam.id} atualizada!", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _refresh_visualization(self, beam):
        self.canvas.axes_shear.cla()
        self.canvas.axes_moment.cla()
        
        x_vals, v_vals, m_vals = [], [], []
        curr_x = 0
        
        for span in beam.spans:
            L = span.length
            x = np.linspace(0, L, 50)
            
            V_esq = span.shear_left
            M_esq = span.moment_left
            q = sum(l.value for l in span.loads if l.load_type == LoadType.DISTRIBUTED)
            
            V = V_esq - q * x
            M = M_esq + V_esq * x - (q * x**2) / 2
            
            x_vals.extend(curr_x + x)
            v_vals.extend(V)
            m_vals.extend(M)
            curr_x += L
        
        self.canvas.axes_shear.plot(x_vals, v_vals, 'b-', label='Cortante')
        self.canvas.axes_shear.fill_between(x_vals, v_vals, 0, color='blue', alpha=0.1)
        self.canvas.axes_shear.set_ylabel("Cortante (kN)")
        self.canvas.axes_shear.grid(True, alpha=0.3)
        self.canvas.axes_shear.set_title(f"Diagramas: {beam.id}")
        
        self.canvas.axes_moment.plot(x_vals, m_vals, 'r-', label='Momento')
        self.canvas.axes_moment.fill_between(x_vals, m_vals, 0, color='red', alpha=0.1)
        self.canvas.axes_moment.invert_yaxis()
        self.canvas.axes_moment.set_ylabel("Momento (kNm)")
        self.canvas.axes_moment.set_xlabel("Distância (m)")
        self.canvas.axes_moment.grid(True, alpha=0.3)
        self.canvas.draw()
        
        self.table_detail.setRowCount(0)
        for i, span in enumerate(beam.spans):
            det = getattr(span, 'detailing_results', None)
            if not det: continue
            
            self._add_detail_row(f"Vão {i+1} Positiva", det['positive'])
            self._add_detail_row(f"Vão {i+1} Estribos", det['stirrups'], is_stirrup=True)
            self._add_detail_row(f"Apoio Esq (Neg)", det['negative_left'])
            self._add_detail_row(f"Apoio Dir (Neg)", det['negative_right'])

    def _add_detail_row(self, label, data, is_stirrup=False):
        row = self.table_detail.rowCount()
        self.table_detail.insertRow(row)
        
        if is_stirrup:
            desc = f"Ø{data.diameter_mm} c/{data.spacing_cm}"
            area = "-"
        else:
            if data.count > 0:
                desc = f"{data.count} Ø{data.diameter_mm}"
                if hasattr(data, 'anchorage_length_cm') and data.anchorage_length_cm > 0:
                     desc += f" (Lb={data.anchorage_length_cm})"
                area = f"{data.area_provided_cm2:.2f}"
            else:
                desc = "Mínima"
                area = "0.00"
                
        self.table_detail.setItem(row, 0, QTableWidgetItem(label))
        self.table_detail.setItem(row, 1, QTableWidgetItem(desc))
        self.table_detail.setItem(row, 2, QTableWidgetItem(area))
        
        item_status = QTableWidgetItem(data.status)
        if "OK" in data.status:
            item_status.setForeground(QColor("green"))
        else:
            item_status.setForeground(QColor("red"))
        self.table_detail.setItem(row, 3, item_status)

    def _run_optimization_gui(self):
        if not self.selected_beam_id: return
        from app.engines.optimizer import OptimizerEngine
        optimizer = OptimizerEngine()
        beam = self.current_beams[self.selected_beam_id]
        
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            report = optimizer.optimize_beam(beam)
            if "error" in report:
                QMessageBox.warning(self, "Aviso", report["error"])
                return
            
            orig = report["original"]
            best = report["best"]
            
            msg = (f"<h3>Resultado da Otimização</h3>"
                   f"A altura ideal encontrada foi <b>{best['h']} cm</b>.<br><br>"
                   f"<ul>"
                   f"<li>Custo Atual: R$ {orig['cost']:.2f}</li>"
                   f"<li>Custo Otimizado: R$ {best['cost']:.2f}</li>"
                   f"<li><b>Economia: R$ {orig['cost'] - best['cost']:.2f}</b></li>"
                   f"</ul>"
                   f"Deseja aplicar essa seção agora?")
            
            reply = QMessageBox.question(self, "Otimização", msg, 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.spin_h.setValue(int(best['h']))
                self._manual_update()
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    # --- LÓGICA DE EXPORTAÇÃO E PILARES ---

    def _load_pillar_table(self):
        """Calcula as reações e preenche a tabela para edição."""
        if not self.current_beams:
            QMessageBox.warning(self, "Aviso", "Nenhum projeto carregado.")
            return
            
        from app.services.report_exporter import DataExporter
        exporter = DataExporter()
        
        try:
            # Obtém os dados (lista de dicts)
            self.pillar_data_cache = exporter.calculate_reactions(self.current_beams)
            
            # Preenche a Tabela
            self.table_pillars.setRowCount(0)
            for row, p in enumerate(self.pillar_data_cache):
                self.table_pillars.insertRow(row)
                
                # ID (Editável)
                self.table_pillars.setItem(row, 0, QTableWidgetItem(p['id_estimado']))
                
                # Coord (Apenas leitura)
                coord_str = f"({p['coordenada']['x']}, {p['coordenada']['y']})"
                item_coord = QTableWidgetItem(coord_str)
                item_coord.setFlags(item_coord.flags() ^ Qt.ItemFlag.ItemIsEditable) # Bloqueia edição
                self.table_pillars.setItem(row, 1, item_coord)
                
                # Fz
                self.table_pillars.setItem(row, 2, QTableWidgetItem(str(p['cargas_servico']['Fz_kN'])))
                
                # Mx, My (Novas colunas para engaste!)
                self.table_pillars.setItem(row, 3, QTableWidgetItem(str(p['cargas_servico']['Mx_kNm'])))
                self.table_pillars.setItem(row, 4, QTableWidgetItem(str(p['cargas_servico']['My_kNm'])))
                
                # Origem
                origem_str = ", ".join(p['origem_cargas'])
                self.table_pillars.setItem(row, 5, QTableWidgetItem(origem_str))
            
            self.statusBar().showMessage(f"Carregados {len(self.pillar_data_cache)} pilares.")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro ao calcular pilares", str(e))

    def _export_pillars_json(self):
        """Lê a tabela (com nomes editados) e salva o JSON."""
        if self.table_pillars.rowCount() == 0:
            QMessageBox.warning(self, "Aviso", "Carregue a tabela primeiro (Botão 'Calcular Reações').")
            return
            
        # Reconstrói a lista de dados a partir da tabela editada
        export_data = []
        for row in range(self.table_pillars.rowCount()):
            # Lê o ID que o usuário pode ter editado
            new_id = self.table_pillars.item(row, 0).text()
            
            # Recupera os dados originais do cache para não perder precisão ou outros campos
            # Assume que a ordem das linhas não mudou
            original_data = self.pillar_data_cache[row]
            
            # Cria cópia e atualiza ID
            pillar_entry = original_data.copy()
            pillar_entry['id_estimado'] = new_id
            
            export_data.append(pillar_entry)
            
        # Salva
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar JSON de Pilares", "pilares_input.json", "JSON (*.json)")
        if file_path:
            from app.services.report_exporter import DataExporter
            exporter = DataExporter(output_path=file_path)
            success, msg = exporter.save_json(export_data, file_path)
            
            if success:
                QMessageBox.information(self, "Sucesso", f"Exportado com sucesso para:\n{file_path}")
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _save_memorial_file(self):
        """Gera e salva o memorial completo."""
        if not self.current_beams:
            QMessageBox.warning(self, "Aviso", "Nenhum projeto carregado.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar Memorial", "memorial_vigas.md", "Markdown (*.md);;Text (*.txt)")
        if not file_path:
            return

        try:
            text = "# MEMORIAL DE CÁLCULO ESTRUTURAL\n"
            text += "Norma: NBR 6118:2023\n"
            text += "="*60 + "\n\n"
            
            for b_id, beam in self.current_beams.items():
                text += f"## VIGA: {b_id}\n"
                if beam.spans:
                    text += f"* Seção: {beam.spans[0].section.bw} x {beam.spans[0].section.h} cm\n"
                text += f"* Vãos: {len(beam.spans)}\n"
                text += "-"*40 + "\n"
                
                for i, span in enumerate(beam.spans):
                    det = getattr(span, 'detailing_results', None)
                    res = getattr(span, 'design_results', {})
                    els = getattr(span, 'els_results', None)
                    
                    text += f"### Vão {i+1} (L = {span.length:.2f} m)\n\n"
                    
                    if res:
                        text += f"**1. Solicitações (ELU):**\n"
                        text += f"- Md máx: {res.get('Md_max', 0):.2f} kNm\n"
                        text += f"- Vsd máx: {res.get('V_sd', 0):.2f} kN\n\n"
                    
                    if els:
                        text += f"**2. Verificação (ELS):**\n"
                        text += f"- Flecha Total: {els.deflection_total:.2f} mm (Limite: {els.deflection_limit:.2f} mm) -> {els.status_deflection}\n"
                        text += f"- Fissuração: {els.wk_calc:.3f} mm (Limite: {els.wk_limit} mm) -> {els.status_crack}\n\n"
                    
                    if det:
                        text += f"**3. Detalhamento:**\n"
                        pos = det['positive']
                        est = det['stirrups']
                        text += f"- Positiva: {pos.count} Ø{pos.diameter_mm:.1f} mm (As ef: {pos.area_provided_cm2:.2f} cm²)\n"
                        if hasattr(pos, 'anchorage_length_cm') and pos.anchorage_length_cm > 0:
                            text += f"  - Lb nec: {pos.anchorage_length_cm} cm\n"
                        
                        text += f"- Estribos: Ø{est.diameter_mm:.1f} c/{est.spacing_cm} cm\n"
                        
                        neg_esq = det['negative_left']
                        if neg_esq.count > 0:
                             text += f"- Neg. Esq: {neg_esq.count} Ø{neg_esq.diameter_mm:.1f} mm\n"

                        neg_dir = det['negative_right']
                        if neg_dir.count > 0:
                             text += f"- Neg. Dir: {neg_dir.count} Ø{neg_dir.diameter_mm:.1f} mm\n"
                    
                    text += "\n" + "-"*40 + "\n"
                
                text += "\n" + "="*60 + "\n\n"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            QMessageBox.information(self, "Sucesso", f"Memorial salvo em:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro ao salvar", str(e))