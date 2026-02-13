
import simflow.variables


def test_float():
    fv = simflow.variables.FloatVariable( 'F', 1.0 )
    fv.value = 1.23

    fv = simflow.variables.FloatVariable( 'F', 4.0, upper_bound=5., lower_bound=4. )
    fv.value = 4.3

def test_intset():
    iv = simflow.variables.IntSetVariable( 'I', 1, [1,2,7] )

    iv.value = 7

def test_strset():
    iv = simflow.variables.StrSetVariable( 'I', 'foo', ['foo','fam'] )

    iv.value = 'fam'

if __name__ == "__main__":
    test_float()
    test_intset()
    test_strset()
