import math
from app.models.entities import Beam, BeamSpan, MaterialType

class ELUDesignEngine:
    """
    Motor de Dimensionamento no Estado Limite Último (ELU) conforme NBR 6118:2023.
    Responsável por calcular as armaduras longitudinais (Flexão) e transversais (Cisalhamento).
    """

    def __init__(self, gamma_c=1.4, gamma_s=1.15, gamma_f=1.4):
        self.gamma_c = gamma_c # Coeficiente de segurança concreto
        self.gamma_s = gamma_s # Coeficiente de segurança aço
        self.gamma_f = gamma_f # Coeficiente de majoração de esforços

    def run_design(self, beam: Beam):
        """
        Itera sobre todos os vãos da viga e calcula as armaduras necessárias.
        """
        for span in beam.spans:
            self._design_flexure(span)
            self._design_shear(span)

    def _design_flexure(self, span: BeamSpan):
        """
        Calcula a armadura longitudinal para os momentos fletores máximos (Apoios e Vão).
        Considera seção retangular.
        """
        # 1. Obter Materiais e Geometria
        fcd = span.material.get_fcd() # kN/cm²
        fyd = span.material.fyk / self.gamma_s / 10.0 # kN/cm²
        
        b = span.section.bw # cm
        h = span.section.h  # cm
        d = h - 4.0 # Altura útil estimada (d = h - cobrimento - estribo - meio fio) -> Ajustar conforme necessidade
        
        # 2. Identificar Momentos de Cálculo (Majorados)
        # O Solver nos dá momentos característicos (ou já de cálculo dependendo da carga inputada, 
        # mas assumimos input característico aqui).
        # Vamos dimensionar para o pior caso em cada seção crítica (Esq, Vão, Dir)
        
        # Momento no Vão (Estimativa simplificada qL^2/8 menos média dos apoios para viga contínua)
        # Para ser preciso, deveríamos varrer o diagrama de momentos. 
        # Aqui usaremos os valores nodais do solver e uma estimativa de positivo.
        
        # Momentos negativos (Apoios) - O solver dá o sinal. Módulo para dimensionar armadura superior.
        Md_neg_esq = abs(span.moment_left) * self.gamma_f
        Md_neg_dir = abs(span.moment_right) * self.gamma_f
        
        # Estimativa de Momento Positivo Máximo (Vão)
        # M_pos_max approx M_isostático - (M_esq + M_dir)/2
        # M_isostático = (q * L^2) / 8 (Considerando carga distribuída predominante)
        q_total = sum([l.value for l in span.loads if l.load_type.name == 'DISTRIBUTED'])
        L = span.length
        M0 = (q_total * L**2) / 8
        Md_pos_vao = max(0, (M0 - (abs(span.moment_left) + abs(span.moment_right))/2)) * self.gamma_f

        # 3. Calcular Armaduras
        # Armadura Superior (Negativa) - Apoio Esquerdo
        as_sup_esq = self._calc_reinforcement_area(Md_neg_esq, b, d, fcd, fyd)
        
        # Armadura Superior (Negativa) - Apoio Direito
        as_sup_dir = self._calc_reinforcement_area(Md_neg_dir, b, d, fcd, fyd)
        
        # Armadura Inferior (Positiva) - Vão
        as_inf_vao = self._calc_reinforcement_area(Md_pos_vao, b, d, fcd, fyd)

        # 4. Verificar Armadura Mínima (NBR 6118 Tabela 17.3.5)
        # rho_min para fck 25 = 0.15%
        as_min = 0.0015 * b * h 
        
        # Armazenar Resultados no Span (Poderíamos criar um objeto ReinforcementResult mais complexo)
        # Aqui, vamos adicionar atributos dinamicamente ou usar um dicionário de resultados
        span.design_results = {
            "As_sup_esq": max(as_sup_esq, as_min) if Md_neg_esq > 0.1 else 0, # Se for apoio de extremidade livre, pode ser 0
            "As_sup_dir": max(as_sup_dir, as_min) if Md_neg_dir > 0.1 else 0,
            "As_inf_vao": max(as_inf_vao, as_min),
            "Md_max": max(Md_neg_esq, Md_neg_dir, Md_pos_vao)
        }

    def _calc_reinforcement_area(self, Md_kNm, b_cm, d_cm, fcd_kNcm2, fyd_kNcm2):
        """
        Calcula As para seção retangular (Domínios 2, 3).
        """
        if Md_kNm <= 0.01: return 0.0

        Md_kNcm = Md_kNm * 100
        
        # Equação adimensional (Kmd)
        # Md = 0.68 * b * x * fcd * (d - 0.4x)
        # Kmd = Md / (b * d^2 * fcd)
        kmd = Md_kNcm / (b_cm * (d_cm**2) * fcd_kNcm2)

        # Limite entre domínios 3 e 4 (x/d = 0.45 para fck <= 50)
        # Se kmd > limite, armadura dupla ou aumentar seção.
        # Kmd limite approx 0.251 para x/d = 0.45
        if kmd > 0.251:
            # Simplificação: Retornar erro ou calcular armadura dupla
            # Vamos limitar e avisar (em um software real, lançaria exceção ou calcularia As')
            print(f"AVISO: Kmd {kmd:.3f} muito alto (Domínio 4). Aumente a seção.")
            return (Md_kNcm / (0.9 * d_cm * fyd_kNcm2)) * 1.5 # Penalidade estimativa
        
        # Calcular braço de alavanca z
        # z = d * (1 - 0.4 * x/d)
        # Resolvendo Bhaskara para achar x/d (beta_x) em função de Kmd:
        # beta_x = (1 - sqrt(1 - 2.35 * Kmd)) / 1.176 ... Fórmula aproximada do ábaco
        
        # Solução exata da eq de equilíbrio:
        # 0.272 * beta_x^2 - 0.68 * beta_x + Kmd = 0
        try:
            val_sqrt = 1 - (4 * 0.272 * kmd) / (0.68**2)
            if val_sqrt < 0: return 999.0 # Impossível
            
            beta_x = (0.68 - math.sqrt(0.68**2 - 4 * 0.272 * kmd)) / (2 * 0.272)
        except:
            beta_x = 0.5
            
        z = d_cm * (1 - 0.4 * beta_x)
        
        # As = Md / (z * fyd)
        As = Md_kNcm / (z * fyd_kNcm2)
        return As

    def _design_shear(self, span: BeamSpan):
        """
        Calcula armadura transversal (Estribos) - Modelo I da NBR 6118.
        Considera Vkt (cisalhamento máximo).
        """
        # Obter esforço cortante máximo de cálculo no vão
        # Conservadoramente: Maior valor entre V_esq e V_dir
        Vd_max = max(abs(span.shear_left), abs(span.shear_right)) * self.gamma_f
        
        fcd = span.material.get_fcd()
        fctd = (0.21 * (span.material.fck ** (2/3))) / self.gamma_c / 10.0 # kN/cm²
        b = span.section.bw
        d = span.section.h - 4.0
        
        # 1. Verificação da Biela Comprimida (V_Rd2)
        # alpha_v2 = 1 - (fck / 250)
        alpha_v2 = 1 - (span.material.fck / 250)
        V_rd2 = 0.27 * alpha_v2 * fcd * b * d # kN (Modelo I)
        
        status_biela = "OK"
        if Vd_max > V_rd2:
            status_biela = "FALHA (Esmagamento Biela)"
            # Em software real, pararia o processo
        
        # 2. Cálculo da Armadura (V_sw = V_sd - V_c)
        # V_c0 = 0.6 * fctd * b * d (Cisalhamento absorvido pelo concreto simples)
        V_c = 0.6 * fctd * b * d
        
        V_sw = max(0, Vd_max - V_c)
        
        # Asw/s = V_sw / (0.9 * d * fyd_estribo)
        # Assumindo estribo vertical (90 graus)
        # fyd do estribo geralmente limitado a 435 MPa (CA-50 ou CA-60) mesmo sendo 500 ou 600
        fyd_transv = 43.5 # kN/cm²
        
        Asw_s_calc = V_sw / (0.9 * d * fyd_transv) # cm²/cm
        
        # Armadura Mínima de Cisalhamento
        # rho_sw_min = 0.2 * fct,m / fywk
        fctm = 0.3 * (span.material.fck ** (2/3)) / 10.0 # kN/cm²
        Asw_s_min = (0.2 * fctm / 50.0) * b # cm²/cm (fywk 500 MPa)
        
        Asw_s_final = max(Asw_s_calc, Asw_s_min)
        
        # Armazenar
        if not hasattr(span, "design_results"): span.design_results = {}
        span.design_results["V_sd"] = Vd_max
        span.design_results["Asw_s_req"] = Asw_s_final # cm²/cm
        span.design_results["Status_Biela"] = status_biela

# Bloco de teste
if __name__ == "__main__":
    from app.models.entities import Material, CrossSection
    
    # Criar cenário fictício
    mat = Material(name="C25", type=MaterialType.CONCRETE, fck=25)
    sec = CrossSection(bw=20, h=50)
    span = BeamSpan(id=1, length=5.0, section=sec, material=mat)
    
    # Simular esforços vindos do solver (kN e kNm)
    span.moment_left = -25.0
    span.moment_right = -30.0
    span.shear_left = 45.0
    span.shear_right = -45.0
    # Adicionar carga para cálculo do vão
    from app.models.entities import Load, LoadType
    span.loads.append(Load(LoadType.DISTRIBUTED, 15.0, 0, 5)) 

    beam = Beam(id="Test")
    beam.spans.append(span)

    engine = ELUDesignEngine()
    engine.run_design(beam)
    
    res = span.design_results
    print(f"Dimensionamento Viga 20x50 (C25):")
    print(f"Momentos Máximos (Md): {res['Md_max']:.2f} kNm")
    print(f"As Negativo Esq: {res['As_sup_esq']:.2f} cm²")
    print(f"As Positivo Vão: {res['As_inf_vao']:.2f} cm²")
    print(f"Estribos (Asw/s): {res['Asw_s_req']:.4f} cm²/cm ({res['Asw_s_req']*100:.2f} cm²/m)")
    print(f"Status Biela: {res['Status_Biela']}")