import os
import sys

# Correção de Path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.controllers.beam_controller import BeamController
from app.ui.plots import BeamPlotter
from app.services.report_exporter import DataExporter

class CommandLineInterface:
    def __init__(self):
        self.controller = BeamController()
        self.current_beams = {} 

    def run(self):
        while True:
            self._clear_screen()
            print("==================================================")
            print("    PyViga - Dimensionamento e Detalhamento       ")
            print("==================================================")
            print("1. Processar arquivo de Lajes (JSON)")
            print("2. Visualizar Gráficos (DEC/DMF)")
            print("3. Exportar Cargas para Pilares (JSON)")
            print("4. Otimizar Seção da Viga")
            print("5. Modo Demo")
            print("0. Sair")
            print("==================================================")
            
            if self.current_beams:
                print(f"Status: {len(self.current_beams)} vigas carregadas.")
            else:
                print("Status: Nenhuma viga carregada.")
            print("==================================================")

            choice = input("Opção: ")
            
            if choice == "1":
                self._menu_process_file()
            elif choice == "2":
                if self.current_beams: self._menu_plots(self.current_beams)
            elif choice == "3":
                if self.current_beams: self._menu_export()
            elif choice == "4":
                if self.current_beams: self._menu_optimize()
            elif choice == "5":
                self._menu_demo()
            elif choice == "0":
                sys.exit()

    def _menu_process_file(self):
        path = input("\nArquivo JSON (ex: vigas.json): ")
        if not os.path.exists(path):
            print("Arquivo não encontrado!")
            input("Enter...")
            return

        print("\nProcessando...")
        self.current_beams = self.controller.run_batch_analysis(path)
        self._print_detailed_report(self.current_beams)
        input("\nPressione Enter para voltar...")

    def _print_detailed_report(self, beams):
        print("\n" + "="*80)
        print(f"{'RELATÓRIO DE DETALHAMENTO DE VIGAS':^80}")
        print("="*80)
        
        for b_id, beam in beams.items():
            print(f"\n>> VIGA: {beam.id} (Vãos: {len(beam.spans)})")
            
            for i, span in enumerate(beam.spans):
                print(f"   Vão {i+1}: {span.length:.2f}m | Seção {span.section.bw}x{span.section.h} cm")
                print(f"   {'-'*70}")
                
                # VERIFICAÇÃO TÉCNICA
                res = getattr(span, 'design_results', {})
                els = getattr(span, 'els_results', None)
                
                if els:
                    status_wk = "✅" if els.status_crack == "OK" else "❌"
                    status_def = "✅" if els.status_deflection == "OK" else "❌"
                    print(f"   [ESTADO LIMITE DE SERVIÇO]")
                    print(f"     Fissuração: {status_wk} {els.wk_calc:.2f}mm (Lim: {els.wk_limit}mm)")
                    print(f"     Flecha:     {status_def} {els.deflection_total:.2f}mm (Lim: {els.deflection_limit:.2f}mm)")
                
                print(f"   [DETALHAMENTO DA ARMADURA]")
                det = getattr(span, 'detailing_results', None)
                
                if det:
                    est = det['stirrups']
                    print(f"     ESTRIBOS:   Ø{est.diameter_mm:.1f} c/{est.spacing_cm} cm ({est.status})")
                    
                    pos = det['positive']
                    print(f"     POSITIVA:   {pos.count} Ø{pos.diameter_mm:.1f} mm (As: {pos.area_provided_cm2:.2f} cm²)")
                    if pos.count > 0:
                        print(f"                 Ancoragem reta necessária: {pos.anchorage_length_cm} cm")

                    neg_esq = det['negative_left']
                    if neg_esq.count > 0:
                        print(f"     NEG. ESQ:   {neg_esq.count} Ø{neg_esq.diameter_mm:.1f} mm (Lb: {neg_esq.anchorage_length_cm} cm)")
                    else:
                        print(f"     NEG. ESQ:   Mínima/Construtiva")

                    neg_dir = det['negative_right']
                    if neg_dir.count > 0:
                        print(f"     NEG. DIR:   {neg_dir.count} Ø{neg_dir.diameter_mm:.1f} mm (Lb: {neg_dir.anchorage_length_cm} cm)")
                    
                    skin = det.get('skin')
                    if skin and "Não necessário" not in skin.status:
                         print(f"     PELE:       {skin.status} Ø{skin.diameter_mm:.1f} mm")
                else:
                    print("     [!] Detalhamento não disponível.")
                
                print(f"   {'-'*70}")

    def _menu_plots(self, beams):
        while True:
            beam_id = input("\nID da viga para gráfico (ou 'v' voltar): ")
            if beam_id.lower() == 'v': break
            if beam_id in beams:
                BeamPlotter.plot_results(beams[beam_id])
            else:
                print("ID inválido.")

    def _menu_export(self):
        exporter = DataExporter()
        exporter.export_pillar_loads(self.current_beams)
        input("Enter...")

    def _menu_optimize(self):
        print("\n--- Otimização de Seção ---")
        beam_id = input("Digite o ID da viga para otimizar: ")
        if beam_id in self.current_beams:
            self.controller.run_optimization(beam_id, self.current_beams)
        else:
            print("Viga não encontrada.")
        input("\nPressione Enter para continuar...")

    def _menu_demo(self):
        import json
        filename = "demo_vigas.json"
        data = {
            "V_Demo": {
                "id": "V_Demo",
                "geometria_estimada": "20x50",
                "coordenadas_globais": { "comprimento_total": 6.0 },
                "cargas_distribuidas": [
                    {
                        "origem": "Exemplo",
                        "tipo": "Reacao Vertical",
                        "valor_kNm": 15.0,
                        "posicao_na_viga": { "inicio": 0.0, "fim": 6.0, "comprimento": 6.0 }
                    }
                ]
            }
        }
        with open(filename, "w") as f:
            json.dump(data, f)
        print(f"Arquivo '{filename}' criado com sucesso!")
        input("Pressione Enter para continuar...")

    def _clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == "__main__":
    cli = CommandLineInterface()
    cli.run()