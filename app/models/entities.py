from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum
import math

# --- ENUMS E VALUE OBJECTS ---

class MaterialType(Enum):
    CONCRETE = "CONCRETE"
    STEEL = "STEEL"

class LoadType(Enum):
    DISTRIBUTED = "DISTRIBUTED" # kN/m
    POINT = "POINT"             # kN
    MOMENT = "MOMENT"           # kNm
    TORSION = "TORSION"         # kNm/m

class SupportType(Enum):
    PINNED = "PINNED"   # Rotulado (Apoio Simples)
    FIXED = "FIXED"     # Engastado (Pilar Monolítico)
    FREE = "FREE"       # Livre (Balanço)

@dataclass
class Material:
    name: str
    type: MaterialType
    fck: float = 25.0  # MPa
    fyk: float = 500.0 # MPa
    Ecs: float = 23800.0 # MPa

    def get_fcd(self):
        return (self.fck / 1.4) / 10.0 # kN/cm²

@dataclass
class CrossSection:
    bw: float 
    h: float
    bf: float = 0.0 
    hf: float = 0.0

    @property
    def area(self) -> float:
        area_web = self.bw * self.h
        area_flange = (self.bf - self.bw) * self.hf if self.bf > self.bw else 0
        return area_web + area_flange

    @property
    def inertia(self) -> float:
        return (self.bw * (self.h ** 3)) / 12

# --- CARGAS ---

@dataclass
class Load:
    load_type: LoadType
    value: float
    position_start: float
    position_end: float
    source: str = "Manual"

# --- ELEMENTOS ESTRUTURAIS ---

@dataclass
class Node:
    id: int
    x: float
    y: float = 0.0
    z: float = 0.0
    # [Restrição Y, Restrição Rotação Z]
    # True = Impedido (Apoio), False = Livre
    # Se Engastado: [True, True]
    # Se Articulado: [True, False]
    support_conditions: List[bool] = field(default_factory=lambda: [False, False]) 

@dataclass
class BeamSpan:
    id: int
    length: float
    section: CrossSection
    material: Material
    loads: List[Load] = field(default_factory=list)
    start_node: Optional[Node] = None
    end_node: Optional[Node] = None
    
    moment_left: float = 0.0
    moment_right: float = 0.0
    shear_left: float = 0.0
    shear_right: float = 0.0
    
    # Detalhamento
    design_results: dict = field(default_factory=dict)
    detailing_results: dict = field(default_factory=dict)
    els_results: object = None

@dataclass
class Beam:
    id: str
    spans: List[BeamSpan] = field(default_factory=list)
    nodes: List[Node] = field(default_factory=list)
    direction_vector: tuple = (1.0, 0.0) 
    
    def add_span(self, length: float, section: CrossSection, mat: Material, 
                 start_coord: tuple = (0.0, 0.0), direction: tuple = (1.0, 0.0),
                 start_support: SupportType = SupportType.PINNED,
                 end_support: SupportType = SupportType.PINNED):
        """
        Adiciona um vão com condições de apoio configuráveis.
        """
        span_id = len(self.spans) + 1
        self.direction_vector = direction
        
        # Mapeamento SupportType -> Conditions [Ry, Rz]
        def get_conditions(stype):
            if stype == SupportType.FIXED: return [True, True]    # Preso Y, Preso Rot
            if stype == SupportType.PINNED: return [True, False]  # Preso Y, Livre Rot
            if stype == SupportType.FREE: return [False, False]   # Livre Y, Livre Rot
            return [True, False]

        if not self.nodes:
            # Primeiro Nó
            conds = get_conditions(start_support)
            start_node = Node(id=0, x=start_coord[0], y=start_coord[1], support_conditions=conds)
            self.nodes.append(start_node)
        else:
            start_node = self.nodes[-1]
            # Atualiza condição do nó existente se for mais restritiva (ex: continuidade sobre apoio)
            # Para viga contínua, o nó intermediário geralmente é [True, False] (Apoio simples que permite rotação relativa)
            # A menos que seja um pilar intermediário engastado.
            # Aqui vamos respeitar o input do novo vão se for engaste.
            if start_support == SupportType.FIXED:
                 start_node.support_conditions = [True, True]

        delta_x = length * direction[0]
        delta_y = length * direction[1]
        new_x = start_node.x + delta_x
        new_y = start_node.y + delta_y
        
        conds_end = get_conditions(end_support)
        end_node_id = len(self.nodes)
        end_node = Node(id=end_node_id, x=new_x, y=new_y, support_conditions=conds_end)
        self.nodes.append(end_node)
        
        new_span = BeamSpan(
            id=span_id, 
            length=length, 
            section=section, 
            material=mat,
            start_node=start_node,
            end_node=end_node
        )
        self.spans.append(new_span)
        
        return new_span