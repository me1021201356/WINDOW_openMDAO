# workflow_regular.py only defines the workflow to be built. Class WorkingGroup needs to be imported from another working directory. As an example we provide a working directory in the example folder. Run IEA_borssele_regular.py from the 'example' folder instead

from WINDOW_openMDAO.WakeModel.jensen import JensenWakeFraction, JensenWakeDeficit
from WINDOW_openMDAO.Turbine.Curves import Curves
from openmdao.api import IndepVarComp, Problem, Group, view_model, SqliteRecorder, ExplicitComponent
import numpy as np
from time import time, clock
from WINDOW_openMDAO.input_params import rotor_radius as turbine_radius, max_n_turbines, max_n_substations, interest_rate, central_platform, areas, n_quadrilaterals, separation_equation_y, cutin_wind_speed, cutout_wind_speed, operational_lifetime, number_turbines_per_cable, wind_directions, weibull_shapes, weibull_scales, direction_probabilities, layout, n_turbines, TI_ambient, coll_electrical_efficiency, transm_electrical_efficiency
from WINDOW_openMDAO.WakeModel.WakeMerge.RSS import MergeRSS
from WINDOW_openMDAO.src.api import AEPWorkflow, TIWorkflow, MaxTI, AEP, NumberLayout, MinDistance, WithinBoundaries, RegularLayout, read_layout, read_windrose
from WINDOW_openMDAO.src.Utils.util_components import create_random_layout
from WINDOW_openMDAO.WakeModel.Turbulence.turbulence_wake_models import Frandsen2, DanishRecommendation, Larsen, Frandsen, Quarton
from WINDOW_openMDAO.WaterDepth.water_depth_models import RoughInterpolation, RoughClosestNode
from WINDOW_openMDAO.ElectricalCollection.topology_hybrid_optimiser import TopologyHybridHeuristic
from WINDOW_openMDAO.SupportStructure.teamplay import TeamPlay
from WINDOW_openMDAO.OandM.OandM_models import OM_model1
from WINDOW_openMDAO.Costs.teamplay_costmodel import TeamPlayCostModel
from WINDOW_openMDAO.Finance.LCOE import LCOE
from random import uniform
from WINDOW_openMDAO.src.AbsAEP.aep_fast_component import AEPFast
from WINDOW_openMDAO.src.Utils.transform_quadrilateral import AreaMapping
from WINDOW_openMDAO.input_params import separation_equation_y, windrose_path, ct_curve_path, power_curve_path
import os



class WorkingGroup(Group):
    def __init__(self, fraction_model=JensenWakeFraction, direction_sampling_angle=30.0, windspeed_sampling_points=10, deficit_model=JensenWakeDeficit, merge_model=MergeRSS, turbulence_model=DanishRecommendation, turbine_model=Curves, windrose_file=windrose_path, power_curve_file=power_curve_path, ct_curve_file=ct_curve_path):
        super(WorkingGroup, self).__init__()
        self.fraction_model = fraction_model
        self.deficit_model = deficit_model
        self.merge_model = merge_model
        self.turbine_model = turbine_model
        self.turbulence_model = turbulence_model
        self.windspeed_sampling_points = windspeed_sampling_points
        self.direction_sampling_angle = direction_sampling_angle
        self.n_cases = int((360.0 / self.direction_sampling_angle) * (self.windspeed_sampling_points + 1.0))
        self.windrose_file = windrose_file
        self.power_curve_file = power_curve_file
        self.ct_curve_file = ct_curve_file

    def setup(self):
        indep2 = self.add_subsystem('indep2', IndepVarComp())

        indep2.add_output("areas", val=areas)
        indep2.add_output('layout', val=layout)
        indep2.add_output('layout_x', val=[item[0] for item in layout])
        indep2.add_output('layout_y', val=[item[1] for item in layout])
        indep2.add_output('unitary_layout', shape=(74, 2))
        indep2.add_output('turbine_radius', val=turbine_radius)
        indep2.add_output('n_turbines', val=n_turbines)
        indep2.add_output('n_turbines_p_cable_type', val=number_turbines_per_cable)  # In ascending order, but 0 always at the end. 0 is used for requesting only two or one cable type.
        indep2.add_output('substation_coords', val=central_platform)
        indep2.add_output('n_substations', val=len(central_platform))
        indep2.add_output('coll_electrical_efficiency', val=coll_electrical_efficiency)
        indep2.add_output('transm_electrical_efficiency', val=transm_electrical_efficiency)
        indep2.add_output('operational_lifetime', val=operational_lifetime)
        indep2.add_output('interest_rate', val=interest_rate)

        self.add_subsystem('numberlayout', NumberLayout())
        self.add_subsystem('depths', RoughClosestNode(max_n_turbines))
        self.add_subsystem('platform_depth', RoughClosestNode(max_n_substations))

        self.add_subsystem('AeroAEP', AEPFast(self.direction_sampling_angle, self.windspeed_sampling_points, self.windrose_file, self.power_curve_file, self.ct_curve_file))

        self.add_subsystem('electrical', TopologyHybridHeuristic())

        self.add_subsystem('support', TeamPlay())
        self.add_subsystem('OandM', OM_model1())
        self.add_subsystem('AEP', AEP())
        self.add_subsystem('Costs', TeamPlayCostModel())
        self.add_subsystem('lcoe', LCOE())
        self.add_subsystem('constraint_distance', MinDistance())
        self.add_subsystem('constraint_boundary', WithinBoundaries())

        self.connect("indep2.layout", ["numberlayout.orig_layout", "AeroAEP.layout", "constraint_distance.orig_layout", "constraint_boundary.layout"])
        self.connect("indep2.turbine_radius", "constraint_distance.turbine_radius")
        self.connect("indep2.areas", "constraint_boundary.areas")

        self.connect('numberlayout.number_layout', 'depths.layout')

        self.connect('indep2.n_turbines', ['electrical.n_turbines', 'support.n_turbines', 'Costs.n_turbines'])

        self.connect('numberlayout.number_layout', 'electrical.layout')
        self.connect('indep2.n_turbines_p_cable_type', 'electrical.n_turbines_p_cable_type')
        self.connect('indep2.substation_coords', 'electrical.substation_coords')
        self.connect('indep2.n_substations', 'electrical.n_substations')

        self.connect('depths.water_depths', 'support.depth')
        self.connect('AeroAEP.max_TI', 'support.max_TI')

        self.connect('OandM.availability', 'AEP.availability')
        self.connect('AeroAEP.AEP', ['AEP.aeroAEP', 'OandM.AEP'])
        self.connect('indep2.coll_electrical_efficiency', 'AEP.electrical_efficiency')

        self.connect('platform_depth.water_depths', 'Costs.depth_central_platform', src_indices=[0])

        self.connect('indep2.n_substations', 'Costs.n_substations')
        self.connect('electrical.length_p_cable_type', 'Costs.length_p_cable_type')
        self.connect('electrical.cost_p_cable_type', 'Costs.cost_p_cable_type')
        self.connect('support.cost_support', 'Costs.support_structure_costs')

        self.connect('indep2.substation_coords', 'platform_depth.layout')

        self.connect('Costs.investment_costs', 'lcoe.investment_costs')
        self.connect('OandM.annual_cost_O&M', 'lcoe.oandm_costs')
        self.connect('Costs.decommissioning_costs', 'lcoe.decommissioning_costs')
        self.connect('AEP.AEP', 'lcoe.AEP')
        self.connect('indep2.transm_electrical_efficiency', 'lcoe.transm_electrical_efficiency')
        self.connect('indep2.operational_lifetime', 'lcoe.operational_lifetime')
        self.connect('indep2.interest_rate', 'lcoe.interest_rate')