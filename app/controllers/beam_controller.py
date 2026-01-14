import sys
import os
import json
from typing import Dict, List

# Adiciona o diretório raiz ao path para permitir imports absolutos
# caso o script seja importado de outros módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.data_importer import PyLajeImporter
from app.services.report_exporter import DataExporter
from app.engines.matrix_solver import MatrixSolver
from app.engines.elu_design import ELUDesignEngine
from app.engines.els_checker import ELSCheckerEngine
from app.engines.bar_selector import BarSelectorEngine
from app.engines.optimizer import OptimizerEngine
from app.models.entities import Beam

class BeamController:
    """
    Controlador Principal do Módulo de Vigas (PyViga).
    Orquestra o fluxo de dados: Importação -> Análise -> Dimensionamento -> Verificação -> Otimização.
    """

    def __init__(self):
        # Inicializa os motores de cálculo com configurações padrão
        self.elu_engine = ELUDesignEngine(gamma_c=1.4, gamma_s=1.15)
        self.els_engine = ELSCheckerEngine(caa=2) # Default: Classe de Agressividade II

    def run_batch_analysis(self, json_file_path: str) -> Dict[str, Beam]:
        """
        Executa o fluxo completo para todas as vigas definidas no arquivo JSON.
        """
        if not os.path.exists(json_file_path):
            print(f"[ERRO] Arquivo não encontrado: {json_file_path}")
            return {}

        print(f"--- Iniciando Processamento de Lote: {os.path.basename(json_file_path)} ---")
        
        # 1. Importação de Dados
        importer = PyLajeImporter(json_file_path)
        try:
            beams = importer.load_beams()
            print(f"Importado(s) {len(beams)} viga(s) com sucesso.")
        except Exception as e:
            print(f"ERRO FATAL na importação: {e}")
            return {}

        results = {}

        # 2. Loop de Processamento por Viga
        for beam_id, beam in beams.items():
            print(f"\n>> Processando Viga: {beam.id} ...")
            
            try:
                self._process_single_beam(beam)
                results[beam_id] = beam
                print(f"   [OK] Análise concluída para {beam.id}")
            except Exception as e:
                print(f"   [ERRO] Falha ao processar {beam.id}: {e}")
                # Em produção, usar logging
                # import traceback
                # traceback.print_exc()
        
        return results

    def _process_single_beam(self, beam: Beam):
        """
        Executa o pipeline de cálculo para uma única viga.
        """
        # PASSO A: Análise Estrutural (Matricial)
        solver = MatrixSolver(beam)
        solver.solve()
        
        # PASSO B: Dimensionamento ELU
        self.elu_engine.run_design(beam)
        
        # PASSO C: Verificação ELS
        self.els_engine.run_checks(beam)

        # PASSO D: Detalhamento Lógico Completo
        selector = BarSelectorEngine()
        
        for span in beam.spans:
            if not hasattr(span, "design_results"): continue
            res = span.design_results
            
            # Recuperar FCK do material do vão
            fck_val = span.material.fck
            
            # 1. Armadura Inferior (Positiva - Vão)
            as_pos = res.get("As_inf_vao", 0.0)
            det_pos = selector.select_longitudinal(as_pos, span.section.bw, fck_mpa=fck_val)
            
            # 2. Armadura Superior (Negativa - Apoios)
            as_neg_esq = res.get("As_sup_esq", 0.0)
            det_neg_esq = selector.select_longitudinal(as_neg_esq, span.section.bw, is_top=True, fck_mpa=fck_val)
            
            as_neg_dir = res.get("As_sup_dir", 0.0)
            det_neg_dir = selector.select_longitudinal(as_neg_dir, span.section.bw, is_top=True, fck_mpa=fck_val)
            
            # 3. Pele e Estribos (Mantém igual)
            det_pele = selector.select_skin_reinforcement(span.section.h, span.section.bw)
            asw_req = res.get("Asw_s_req", 0.0)
            det_shear = selector.select_stirrup(asw_req, span.section.bw, span.section.h)
            
            span.detailing_results = {
                "positive": det_pos,
                "negative_left": det_neg_esq,
                "negative_right": det_neg_dir,
                "skin": det_pele,
                "stirrups": det_shear
            }

    def run_optimization(self, beam_id: str, beams_dict: Dict[str, Beam]):
        """
        Executa a rotina de otimização para uma viga específica.
        """
        if beam_id not in beams_dict:
            print("Viga não encontrada na memória (Processe o arquivo primeiro).")
            return

        beam = beams_dict[beam_id]
        optimizer = OptimizerEngine()
        
        try:
            report = optimizer.optimize_beam(beam)
        except Exception as e:
            print(f"Erro crítico durante otimização: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n" + "="*60)
        print(f"RELATÓRIO DE OTIMIZAÇÃO: {beam.id}")
        print("="*60)
        
        if "error" in report:
            print(f"Erro: {report['error']}")
            return

        orig = report["original"]
        best = report["best"]
        
        print(f"{'CENÁRIO':<15} | {'SEÇÃO (cm)':<12} | {'AÇO (kg)':<10} | {'CUSTO EST.(R$)':<15}")
        print("-" * 60)
        
        # Tratamento seguro caso a original tenha falhado na otimização (recalculo)
        if orig:
            orig_h = orig['h']
            orig_steel = orig.get('steel_kg', 'N/A')
            orig_cost = orig.get('cost', 'N/A')
            print(f"{'ATUAL':<15} | {beam.spans[0].section.bw}x{orig_h:<9} | {orig_steel:<10} | R$ {orig_cost}")
        else:
            print(f"{'ATUAL':<15} | Falha ao recalcular original")
            
        print(f"{'OTIMIZADO':<15} | {beam.spans[0].section.bw}x{best['h']:<9} | {best['steel_kg']:<10} | R$ {best['cost']:.2f}")
        print("-" * 60)
        
        if orig and isinstance(orig.get('cost'), (int, float)):
            economy = orig['cost'] - best['cost']
            print(f"RECOMENDAÇÃO: {report['recommendation']}")
            if economy > 0:
                print(f"ECONOMIA TOTAL: R$ {economy:.2f}")
        else:
            print(f"RECOMENDAÇÃO: {report['recommendation']}")
            
        print("="*60)

    def export_pillar_loads(self, beams: Dict[str, Beam]):
        """
        Exporta as cargas para o arquivo de pilares.
        """
        exporter = DataExporter()
        exporter.export_pillar_loads(beams)

    def generate_report(self, beams: Dict[str, Beam]):
        """
        Gera um relatório simplificado (usado como fallback ou resumo rápido).
        O relatório detalhado está sendo gerado pelo CLI atualmente.
        """
        # Método mantido para compatibilidade, mas o CLI tem sua própria visualização detalhada.
        pass