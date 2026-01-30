import jinja2

from pathlib import Path
from jinja2 import meta
from simflow.actions import WorkAction
import simflow.args 

"""
The file is for cases where variables / parameters are defined inside the input decks
using the jinja format '{{VAR1}}}'.
"""

class JinjaReplace(WorkAction):
    """
    Action that uses Jinja2 to replace parameters in a file with values.

    The parameters in the file are indicated using double curly braces, e.g., '{{VAR1}}'.
    This action reads a template file, substitutes the parameters with provided values,
    and writes the result to an output file.

    Example:
        A line in the input file:
        '1, 7.8000E-06, {{E}}, 0.3, {{SIG_Y}},  0.0, 0.0, 0.0'
        
        With values E=210.0e9 and SIG_Y=200.0e6, becomes:
        '1, 7.8000E-06, 210.0e9, 0.3, 200.0e6,  0.0, 0.0, 0.0'

    Args:
        name (str): The name of the action.
        input_file_path (str): Path to the input file. This is the template file marked up using jinja delimiters
        output_file_path (str, optional): Path where the processed file will be written. 
            Defaults to simflow.args.RADIOSS_DFLT_FNAME.
        val_format (str, optional): Format string for floating point values (e.g., "%10.3g"). 
            Defaults to "%10.3g".
    """

    @WorkAction.allow_variables_as_arguments
    def __init__( self, name, input_file_path,
                  output_file_path=simflow.args.RADIOSS_DFLT_FNAME, val_format="%10.3g" ):
        WorkAction.__init__(self, name)
        
        self.input_file_path = input_file_path 
        self.output_file_path = output_file_path
        if self.output_file_path is None:
             self.output_file_path = input_file_path
        self.val_format = val_format

        self.par_names = None
        self.par_vals = None
        
        self._get_parameters()

        input_file_path_obj = Path(self.input_file_path).resolve()
        jj_environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(input_file_path_obj.parent)
        )
        self.template = jj_environment.get_template(input_file_path_obj.name)


    def parameter_names( self ):
        """
        Returns the set of parameter names found in the template.

        Returns:
            set: Set of parameter names.
        """
        return self.par_names

    def _get_parameters( self ):
        """
        Extract all undefined variables from a jinja template file.
        
        Parses the template file to identify variables that need to be provided.
        Updates self.par_names and self.undeclared_par_names.

        Raises:
            FileNotFoundError: If the template file does not exist.
        """
        if not Path( self.input_file_path ).exists():
            raise FileNotFoundError(f"template file not found: {self.input_file_path}")

        with open(self.input_file_path, 'r', encoding='utf-8') as file:
            template_source = file.read()

        self.env = jinja2.Environment()
        ast = self.env.parse(template_source)

        # get undeclared variables (parameters that need to be provided)
        undeclared_vars = jinja2.meta.find_undeclared_variables(ast)

        ast = self.env.parse(template_source)

        variables = set()

        for node in ast.find_all(jinja2.nodes.Name):
            if node.ctx == 'load':  # Loading a variable (not setting)
                variables.add(node.name)

        self.par_names = variables
        self.undeclared_par_names = sorted(list(undeclared_vars))


    def _check_var_dict( self, variable_dict_in, val_format=None ):
        """
        Validates and formats the input variable dictionary.

        Ensures all required parameters are present in the input dictionary.
        Formats floating point values according to val_format.

        Args:
            variable_dict_in (dict): Dictionary of variable names and values.
            val_format (str, optional): Format string for float values.

        Returns:
            dict: A new dictionary with formatted values and ensured keys.
        """
        if variable_dict_in is None : variable_dict_in = {}

        new_vd = variable_dict_in.copy()
        
        for k in new_vd.keys():
            if k not in self.par_names:
                #print( f' *** WARNING Variable \'{k}\' not used in file \'{self.input_file_path}\'.' )
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

        return new_vd

    @WorkAction.assign_variables_values_to_members
    def eval(self, val_dict=None):
        """
        Executes the replacement action.

        Args:
            val_dict (dict, optional): Dictionary of variable values.

        Returns:
            bool: True if successful.
        """
        render_dict = self._check_var_dict(val_dict, val_format=self.val_format)
        content = self.template.render( render_dict )
        
        with open( self.output_file_path, 'w') as f:
            f.write(content)
        return True
