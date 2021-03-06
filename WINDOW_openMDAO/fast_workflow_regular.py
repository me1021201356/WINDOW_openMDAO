# workflow_regular.py only defines the workflow to be built. Class WorkingGroup needs to be imported from another working directory. As an example we provide a working directory in the example folder. Run IEA_borssele_regular.py from the 'example' folder instead

from openmdao.api import IndepVarComp, Group
from WINDOW_openMDAO.input_params import rotor_radius as turbine_radius, max_n_turbines, max_n_substations, interest_rate, central_platform, areas, n_quadrilaterals, separation_equation_y, cutin_wind_speed, cutout_wind_speed, operational_lifetime, number_turbines_per_cable, wind_directions, weibull_shapes, weibull_scales, direction_probabilities, layout, n_turbines, TI_ambient, coll_electrical_efficiency, transm_electrical_efficiency
from WINDOW_openMDAO.src.api import AEP, NumberLayout, MinDistance, WithinBoundaries, RegularLayout
from WINDOW_openMDAO.WaterDepth.water_depth_models import RoughClosestNode
from WINDOW_openMDAO.Finance.LCOE import LCOE



class WorkingGroup(Group):
    def __init__(self, options):
        super(WorkingGroup, self).__init__()
        self.aep_model = options.models.aep
        self.wake_model = options.models.wake
        self.merge_model = options.models.merge
        self.turbine_model = options.models.turbine
        self.turbulence_model = options.models.turbulence
        self.electrical_model = options.models.electrical
        self.support_model = options.models.support
        self.opex_model = options.models.opex
        self.apex_model = options.models.apex
        self.windspeed_sampling_points = options.samples.wind_speeds
        self.direction_sampling_angle = options.samples.wind_sectors_angle
        self.n_cases = int((360.0 / self.direction_sampling_angle) * (self.windspeed_sampling_points + 1.0))
        self.windrose_file = options.input.site.windrose_file
        self.bathymetry_file = options.input.site.bathymetry_file
        self.power_curve_file = options.input.turbine.power_file
        self.ct_curve_file = options.input.turbine.ct_file

    def setup(self):
        indep2 = self.add_subsystem('indep2', IndepVarComp())

        indep2.add_output("areas", val=areas)
        indep2.add_output("downwind_spacing", val=400.0)
        indep2.add_output("crosswind_spacing", val=400.0)
        indep2.add_output("odd_row_shift_spacing", val=0.0)
        indep2.add_output("layout_angle", val=0.0)
        indep2.add_output('turbine_radius', val=turbine_radius)
        indep2.add_output('n_turbines', val=n_turbines)
        indep2.add_output('n_turbines_p_cable_type', val=number_turbines_per_cable)  # In ascending order, but 0 always at the end. 0 is used for requesting only two or one cable type.
        indep2.add_output('substation_coords', val=central_platform)
        indep2.add_output('n_substations', val=len(central_platform))
        indep2.add_output('coll_electrical_efficiency', val=coll_electrical_efficiency)
        indep2.add_output('transm_electrical_efficiency', val=transm_electrical_efficiency)
        indep2.add_output('operational_lifetime', val=operational_lifetime)
        indep2.add_output('interest_rate', val=interest_rate)

        self.add_subsystem('regular_layout', RegularLayout())
        self.add_subsystem('numberlayout', NumberLayout())
        self.add_subsystem('depths', RoughClosestNode(max_n_turbines, self.bathymetry_file))
        self.add_subsystem('platform_depth', RoughClosestNode(max_n_substations, self.bathymetry_file))

        self.add_subsystem('AeroAEP', self.aep_model(self.wake_model, self.turbulence_model, self.merge_model, self.direction_sampling_angle, self.windspeed_sampling_points, self.windrose_file, self.power_curve_file, self.ct_curve_file))

        self.add_subsystem('electrical', self.electrical_model())

        self.add_subsystem('support', self.support_model())
        self.add_subsystem('OandM', self.opex_model())
        self.add_subsystem('AEP', AEP())
        self.add_subsystem('Costs', self.apex_model())
        self.add_subsystem('lcoe', LCOE())


        self.connect("indep2.areas", "regular_layout.area")
        self.connect("indep2.downwind_spacing", "regular_layout.downwind_spacing")
        self.connect("indep2.crosswind_spacing", "regular_layout.crosswind_spacing")
        self.connect("indep2.odd_row_shift_spacing", "regular_layout.odd_row_shift_spacing")
        self.connect("indep2.layout_angle", "regular_layout.layout_angle")
        self.connect("regular_layout.regular_layout", ["numberlayout.orig_layout", "AeroAEP.layout"])

        self.connect("regular_layout.n_turbines_regular", ['electrical.n_turbines', 'support.n_turbines', 'Costs.n_turbines'])

        self.connect('numberlayout.number_layout', 'depths.layout')

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





# # workflow_regular.py only defines the workflow to be built. Class WorkingGroup needs to be imported from another working directory. As an example we provide a working directory in the example folder. Run IEA_borssele_regular.py from the 'example' folder instead

# from WakeModel.jensen import JensenWakeFraction, JensenWakeDeficit
# from Turbine.Curves import Curves
# from openmdao.api import IndepVarComp, Problem, Group, view_model, SqliteRecorder, ExplicitComponent
# import numpy as np
# from time import time, clock
# from input_params import rotor_radius as turbine_radius, max_n_turbines, max_n_substations, interest_rate, central_platform, areas, cutin_wind_speed, cutout_wind_speed, operational_lifetime, number_turbines_per_cable, wind_directions, weibull_shapes, weibull_scales, direction_probabilities, n_turbines, TI_ambient, coll_electrical_efficiency, transm_electrical_efficiency, downwind_spacing, crosswind_spacing, odd_row_shift_spacing, layout_angle
# from WakeModel.WakeMerge.RSS import MergeRSS
# from src.api import AEPWorkflow, TIWorkflow, MaxTI, AEP, NumberLayout, MinDistance, WithinBoundaries, RegularLayout, read_layout, read_windrose
# from WakeModel.Turbulence.turbulence_wake_models import Frandsen2, DanishRecommendation, Larsen, Frandsen, Quarton
# from WaterDepth.water_depth_models import RoughInterpolation, RoughClosestNode
# from ElectricalCollection.topology_hybrid_optimiser import TopologyHybridHeuristic
# from SupportStructure.teamplay import TeamPlay
# from OandM.OandM_models import OM_model1
# from Costs.teamplay_costmodel import TeamPlayCostModel
# from Finance.LCOE import LCOE
# from random import uniform
# from src.AbsAEP.aep_fast_component import AEPFast
 


# class WorkingGroup(Group):
#     def __init__(self, fraction_model=JensenWakeFraction, direction_sampling_angle=6.0, windspeed_sampling_points=7, deficit_model=JensenWakeDeficit, merge_model=MergeRSS, turbulence_model=DanishRecommendation, turbine_model=Curves, windrose_file='Input/weibull_windrose_12unique.dat', power_curve_file='Input/power_dtu10.dat', ct_curve_file='Input/ct_dtu10.dat'):
#         super(WorkingGroup, self).__init__()
#         self.fraction_model = fraction_model
#         self.deficit_model = deficit_model
#         self.merge_model = merge_model
#         self.turbine_model = turbine_model
#         self.turbulence_model = turbulence_model
#         self.windspeed_sampling_points = windspeed_sampling_points
#         self.direction_sampling_angle = direction_sampling_angle
#         self.n_cases = int((360.0 / self.direction_sampling_angle) * (self.windspeed_sampling_points + 1.0))
#         self.windrose_file = windrose_file
#         self.power_curve_file = power_curve_file
#         self.ct_curve_file = ct_curve_file

#     def setup(self):
#         indep2 = self.add_subsystem('indep2', IndepVarComp())

#         indep2.add_output("areas", val=areas)
#         indep2.add_output("downwind_spacing", val=downwind_spacing)
#         indep2.add_output("crosswind_spacing", val=crosswind_spacing)
#         indep2.add_output("odd_row_shift_spacing", val=odd_row_shift_spacing)
#         indep2.add_output("layout_angle", val=layout_angle)

#         indep2.add_output('turbine_radius', val=turbine_radius)
#         indep2.add_output('n_turbines', val=n_turbines)
#         indep2.add_output('n_turbines_p_cable_type', val=number_turbines_per_cable)  # In ascending order, but 0 always at the end. 0 is used for requesting only two or one cable type.
#         indep2.add_output('substation_coords', val=central_platform)
#         indep2.add_output('n_substations', val=len(central_platform))
#         indep2.add_output('coll_electrical_efficiency', val=coll_electrical_efficiency)
#         indep2.add_output('transm_electrical_efficiency', val=transm_electrical_efficiency)
#         indep2.add_output('operational_lifetime', val=operational_lifetime)
#         indep2.add_output('interest_rate', val=interest_rate)

#         self.add_subsystem('regular_layout', RegularLayout())
#         self.add_subsystem('numberlayout', NumberLayout())
#         self.add_subsystem('depths', RoughClosestNode(max_n_turbines, "Input/bathymetry_table.dat"))
#         self.add_subsystem('platform_depth', RoughClosestNode(max_n_substations, "Input/bathymetry_table.dat"))

#         self.add_subsystem('AeroAEP', AEPFast(self.direction_sampling_angle, self.windspeed_sampling_points, self.windrose_file, self.power_curve_file, self.ct_curve_file))

#         self.add_subsystem('electrical', TopologyHybridHeuristic())

#         self.add_subsystem('support', TeamPlay())
#         self.add_subsystem('OandM', OM_model1())
#         self.add_subsystem('AEP', AEP())
#         self.add_subsystem('Costs', TeamPlayCostModel())
#         self.add_subsystem('lcoe', LCOE())

#         self.connect("indep2.areas", "regular_layout.area")
#         self.connect("indep2.downwind_spacing", "regular_layout.downwind_spacing")
#         self.connect("indep2.crosswind_spacing", "regular_layout.crosswind_spacing")
#         self.connect("indep2.odd_row_shift_spacing", "regular_layout.odd_row_shift_spacing")
#         self.connect("indep2.layout_angle", "regular_layout.layout_angle")
#         self.connect("regular_layout.regular_layout", ["numberlayout.orig_layout", "AeroAEP.layout"])
#         self.connect('numberlayout.number_layout', ['depths.layout', 'electrical.layout'])

#         self.connect("regular_layout.n_turbines", ['electrical.n_turbines', 'support.n_turbines', 'Costs.n_turbines'])

#         self.connect('indep2.n_turbines_p_cable_type', 'electrical.n_turbines_p_cable_type')
#         self.connect('indep2.substation_coords', 'electrical.substation_coords')
#         self.connect('indep2.n_substations', 'electrical.n_substations')

#         self.connect('depths.water_depths', 'support.depth')
#         self.connect('AeroAEP.max_TI', 'support.max_TI')

#         self.connect('AeroAEP.AEP', 'OandM.AEP')
#         self.connect('OandM.availability', 'AEP.availability')
#         self.connect('AeroAEP.AEP', 'AEP.aeroAEP')
#         self.connect('indep2.coll_electrical_efficiency', 'AEP.electrical_efficiency')

#         self.connect('platform_depth.water_depths', 'Costs.depth_central_platform', src_indices=[0])

#         self.connect('indep2.n_substations', 'Costs.n_substations')
#         self.connect('electrical.length_p_cable_type', 'Costs.length_p_cable_type')
#         self.connect('electrical.cost_p_cable_type', 'Costs.cost_p_cable_type')
#         self.connect('support.cost_support', 'Costs.support_structure_costs')

#         self.connect('indep2.substation_coords', 'platform_depth.layout')

#         self.connect('Costs.investment_costs', 'lcoe.investment_costs')
#         self.connect('OandM.annual_cost_O&M', 'lcoe.oandm_costs')
#         self.connect('Costs.decommissioning_costs', 'lcoe.decommissioning_costs')
#         self.connect('AEP.AEP', 'lcoe.AEP')
#         self.connect('indep2.transm_electrical_efficiency', 'lcoe.transm_electrical_efficiency')
#         self.connect('indep2.operational_lifetime', 'lcoe.operational_lifetime')
#         self.connect('indep2.interest_rate', 'lcoe.interest_rate')
