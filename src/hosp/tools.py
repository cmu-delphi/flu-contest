# third party
from copy import deepcopy

def create_double_list(obj, dim_x, dim_y):
    """
    create a 2-dimensional list copies for an object.
    all objects in the list are deep copies of the object.

    Args:
        obj - the original object
        dim_x - the first dimension of the double list
        dim_y - the second dimension of the double list
    
    Returns:
        the 2-dimensional list copies of the object
    """
    return [list(deepcopy(obj) for _ in range(dim_y)) for _ in range(dim_x)]

def flatten_double_list(double_list):
    """
    flatten a double list into a single list.
    """
    return [obj for single_list in double_list for obj in single_list]

def write_data(data, file_name):
    """
    write the data to a text file (data.txt) for viewing.

    Args: 
        data - the data source (as python dictionary)
    
    Returns:
        None
    """
    f = open(file_name, mode='w')
    # sort the keys for viewing
    for key in sorted(data.keys()):
        f.write(str(key) + ';' + str(data[key]) + '\n')
    f.close()

def fill_data(data, max_lag):
    """
    fill the series to length 52 (i.e. a year)

    Args:
        data - the data source (included all epiweeks with all lags)
    
    Returns:
        the modified data source
    """
    for _, series in data.items():
        # for all series, repeat the last value until length = 52
        final_val = series[-1]
        series.extend([final_val] * (max_lag - len(series)))
