import os
import numpy as np


from simflow.actions import WorkAction


class CurveSimilarity(WorkAction):

    def __init__( self, name, history_name, experimental_data, similarity_measure='pcm', normalize=False ):
        """ 

        Args:
            name (str): name of this evaluation
            history_name (str): is name of Eval object returning a history ( float[...,2] )
            experimental_data(str):  [num_points,2] is history to match
            similarity_measure=(str):  
            normalize (bool):  pcm always normalize curves
        """

        super().__init__(name, None )
        self.history_name = history_name
        assert experimental_data.ndim == 2, 'Curve data should be of dimension [2,num_time_steps]'
        self.experimental_data = experimental_data
        self.similarity_measure = similarity_measure
        self.normalize = normalize

    def eval( self,  val_dict=None ) -> float:
        """ Evaluate possibly using prev computed evaluation results in val_dict

        Returns:
            similarity_measure (float): 
        """

        import similaritymeasures
        simulation_data = val_dict[ self.history_name ]
        assert simulation_data.ndim == 2, 'Curve data should be of dimension [2,num_time_steps]'

        ed, sd = self.experimental_data.copy(), simulation_data.copy()
        ed_T, sd_T = ed.transpose(), sd.transpose()
        if self.normalize:
            xi, eta, xiP, etaP = similaritymeasures.normalizeTwoCurves( ed[0], ed[1],
                                                                        sd[0], sd[1] )
            ed_T[:,0] = xi
            ed_T[:,1] = eta
            sd_T[:,0] = xiP
            sd_T[:,1] = etaP

        match self.similarity_measure:
            case 'pcm': # material parameter, Witkowski paper
                sim = similaritymeasures.pcm( ed_T, sd_T )
            case 'frechet_dist': # supports N-D data
                # sensitive to outliers, dog-walking distance
                sim = similaritymeasures.frechet_dist( ed_T, sd_T )
            case 'area_between_two_curves': # material parameter
                sim = similaritymeasures.area_between_two_curves( ed_T, sd_T )
            case 'curve_length_measure': # material parameter
                sim = similaritymeasures.curve_length_measure( ed_T, sd_T )
            case 'dtw': # supports N-D data
                # dynamic time warping # support more arguments # returns dtw distance and Cumulative distance matrix
                sim = similaritymeasures.dtw( ed_T, sd_T )
            case 'mae': # supports N-D data # must have same number of data points
                sim = similaritymeasures.mae( ed_T, sd_T )
            case 'mse': # supports N-D data # must have same number of data points
                sim = similaritymeasures.mse( ed_T, sd_T )
            case _:
                exit( f' *** Error Unknown similarity measure {self.similarity_measure}' )

        return sim



