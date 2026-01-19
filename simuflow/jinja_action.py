
import jinja2

from pathlib import Path
from jinja2 import meta

"""
The file is for cases where variables / parameters are defined inside the input decks
using the jinja format '{{VAR1}}}'.
"""

class JinjaFile:
    """
    Mixin class. Uses jinja to replace parameters with values.
    The parameters are indicated using double curly braces; e.g. '{{VAR1}}'
    So a line of 
    '1, 7.8000E-06, {{E}}, 0.3, {{SIG_Y}},  0.0, 0.0, 0.0'
    becomes
    '1, 7.8000E-06, 210.0e9, 0.3, 200.0e6,  0.0, 0.0, 0.0'
    """

    def __init__( self, fea_file_path ):
        self.fea_file_path = fea_file_path 

        self.par_names = None
        self.par_vals = None
        self._get_parameters()

        fea_file_path = Path(self.fea_file_path).resolve()
        jj_environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(fea_file_path.parent)
        )
        self.template = jj_environment.get_template(fea_file_path.name)


    def parameter_names( self ):
        return self.par_names

    def _get_parameters( self ):
        """extract all undefined variables from a jinja template file.
        To define a variable for jinja: {% set x, y = 10, 20 %}
        """
        if not Path( self.fea_file_path ).exists():
            raise FileNotFoundError(f"template file not found: {self.fea_file_path}")

        with open(self.fea_file_path, 'r', encoding='utf-8') as file:
            template_source = file.read()

        self.env = jinja2.Environment()
        ast = self.env.parse(template_source)

        # get undeclared variables (parameters that need to be provided)
        undeclared_vars = jinja2.meta.find_undeclared_variables(ast)

        ast = self.env.parse(template_source)

        variables = set()

        def visit_name(node):
            if isinstance(node, jinja2.nodes.Name) and node.ctx == 'load':
                variables.add(node.name)

        for node in ast.find_all(jinja2.nodes.Name):
            if node.ctx == 'load':  # Loading a variable (not setting)
                variables.add(node.name)

        self.par_names = variables
        self.undeclared_par_names = sorted(list(undeclared_vars))


    def _check_var_dict( self, variable_dict_in, val_format=None ):
        if variable_dict_in is None : variable_dict_in = {}

        new_vd = variable_dict_in.copy()
        
        for k in new_vd.keys():
            if k not in self.par_names:
                #print( f' *** WARNING Variable \'{k}\' not used in file \'{self.fea_file_path}\'.' )
                pass
        for i,k in enumerate(self.par_names):
            if k not in variable_dict_in.keys() : 
                if self.par_vals is not None:
                    v = self.par_vals[i]
                else:
                    breakpoint()
                    exit( f' *** Error Simulation needs parameter \'{k}\' value declared.' ) # in __init__
                new_vd[k] = v
            
        if val_format is not None: # should be string of certain length in a radioss/dyna file
          for k in new_vd.keys():
            # if k not in self.par_names: # does not matter
            v = new_vd[k]
            if isinstance( v, int ):
                pass
            elif isinstance( v, str ):
                pass
            elif isinstance( v, float ):
                new_vd[k] = val_format%(v)
                #new_vd[k] = "%10.3g"%(v)

        return new_vd


