from numpy import deg2rad, tan, cos, sqrt


def distance_to_front(x, y, theta):
    theta = deg2rad(theta + 180.0)
    return abs(x + tan(theta) * y - 10000000000.0 / cos(theta)) / sqrt(1.0 + tan(theta) ** 2.0)


def order(layout_array, wind_direction):
    distances = []
    for turbine in layout_array:
        distances.append([distance_to_front(turbine[1], turbine[2], wind_direction), turbine[0]])
    distances.sort()
    ordered_indices = [item[1] for item in distances]
    ordered_layout = [layout_array[int(i)] for i in ordered_indices]
    return ordered_layout

if __name__ == '__main__':
    layout = [[0, 5, 0], [1, 3, 0], [2, 7, 1], [3, 2.5, 0]]
    angle = 0.0
    print order(layout, angle)