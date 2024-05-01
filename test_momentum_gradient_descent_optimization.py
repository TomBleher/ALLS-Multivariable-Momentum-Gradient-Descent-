import os
import numpy as np
import random
from pyqtgraph.Qt import QtWidgets
import sys 
import pyqtgraph as pg

# the txt files the code adjusts and uploads 
MIRROR_FILE_PATH = r'dm_parameters.txt'
DISPERSION_FILE_PATH = r'dazzler_parameters.txt'

# open and read the txt files and read the initial values
with open(MIRROR_FILE_PATH, 'r') as file:
    content = file.read()
mirror_values = list(map(int, content.split()))

with open(DISPERSION_FILE_PATH, 'r') as file:
    content = file.readlines()

dispersion_values = {
    0: int(content[0].split('=')[1].strip()),  # 0 is the key for 'order2'
}

class BetatronApplication(QtWidgets.QApplication):
    def __init__(self, *args, **kwargs):
        super(BetatronApplication, self).__init__(*args, **kwargs)

        self.image_groups_dir_run_count = 0
        self.images_processed = 0
        self.count_history = []
        
        # set learning rates for the different optimization variables
        self.focus_learning_rate = 4
        self.second_dispersion_learning_rate = 4
        self.momentum = 0.999

    # ------------ Plotting ------------ #

        # initialize lists to keep track of optimization process
        self.third_dispersion_der_history = []
        self.second_dispersion_der_history = []
        self.focus_der_history = []
        self.total_gradient_history = []

        self.iteration_data = []
        self.der_iteration_data = []
        
        self.count_plot_widget = pg.PlotWidget()
        self.count_plot_widget.setWindowTitle('count optimization')
        self.count_plot_widget.setLabel('left', 'Count')
        self.count_plot_widget.setLabel('bottom', 'Image group iteration')
        self.count_plot_widget.show()
        
        self.main_plot_window = pg.GraphicsLayoutWidget()
        self.main_plot_window.show()

        layout = self.main_plot_window.addLayout(row=0, col=0)

        self.count_plot_widget = layout.addPlot(title='Count vs image group iteration')
        self.total_gradient_plot = layout.addPlot(title='Total gradient vs image group iteration')

        self.plot_curve = self.count_plot_widget.plot(pen='r')
        self.total_gradient_curve = self.total_gradient_plot.plot(pen='y', name='total gradient')

        # y labels of plots
        self.total_gradient_plot.setLabel('left', 'Total Gradient')
        self.count_plot_widget.setLabel('left', 'Image Group Iteration')

        # x label of both plots
        self.count_plot_widget.setLabel('bottom', 'Image Group Iteration')
        self.total_gradient_plot.setLabel('bottom', 'Image Group Iteration')
        
        self.plot_curve.setData(self.iteration_data, self.count_history)
        self.total_gradient_curve.setData(self.der_iteration_data, self.total_gradient_history)

    # ------------ Deformable mirror ------------ #

        self.initial_focus = -240
        self.focus_history = []    
        
        # self.FOCUS_LOWER_BOUND = max(self.initial_focus - 20, -200)
        # self.FOCUS_UPPER_BOUND = min(self.initial_focus + 20, 200)

        self.FOCUS_LOWER_BOUND = -99999
        self.FOCUS_UPPER_BOUND = +99999

        self.tolerance = 1
        
    # ------------ Dazzler ------------ #

        self.DAZZLER_HOST = "192.168.58.7"
        self.DAZZLER_USER = "fastlite"
        self.DAZZLER_PASSWORD = "fastlite"

        # 36100 initial 
        self.initial_second_dispersion = -240
        self.second_dispersion_history = []
        # self.SECOND_DISPERSION_LOWER_BOUND = max(self.initial_second_dispersion - 500, 30000)
        # self.SECOND_DISPERSION_UPPER_BOUND = min(self.initial_second_dispersion + 500, 40000)

        self.SECOND_DISPERSION_LOWER_BOUND = -99999
        self.SECOND_DISPERSION_UPPER_BOUND = +99999

        self.random_direction = [random.choice([-1, 1]) for _ in range(4)]

    def plot_reset(self):
        self.plot_curve.setData(self.iteration_data, self.count_history)
        self.total_gradient_curve.setData(self.der_iteration_data, self.total_gradient_history)

        self.image_group_count_sum = 0
        self.mean_count_per_image_group  = 0
        self.img_mean_count = 0          

    def count_function(self):

        x = self.focus_history[-1]
        y = self.second_dispersion_history[-1]

        count_func = (((0.1 * (x + y)))** 2 * np.sin(0.01 * (x + y)))

        self.count_history.append(count_func) # this is the count for the value
            
    def calc_derivatives(self):
        x = self.focus_history[-1]
        y = self.second_dispersion_history[-1]

        self.count_focus_der = 0.2*(0.1*(x+y))*np.sin(0.01*(x+y))+0.01*(np.cos(0.01*(x+y)))*(0.1*(x+y))**2
        self.count_second_dispersion_der = 0.2*(0.1*(x+y))*np.sin(0.01*(x+y))+0.01*(np.cos(0.01*(x+y)))*(0.1*(x+y))**2

        self.focus_der_history.append(self.count_focus_der)
        self.second_dispersion_der_history.append(self.count_second_dispersion_der)

        self.total_gradient = (self.focus_der_history[-1] + self.second_dispersion_der_history[-1])

        self.total_gradient_history.append(self.total_gradient)
        
        return {"focus":self.count_focus_der,"second_dispersion":self.count_second_dispersion_der}

    def optimize_count(self):
        derivatives = self.calc_derivatives()

        if np.abs(self.focus_learning_rate * derivatives["focus"]) > 1:
            self.new_focus = self.focus_history[-1] + (self.momentum*(self.focus_history[-1]-self.focus_history[-2])) - self.focus_learning_rate*self.focus_der_history[-1]

            self.new_focus = np.clip(self.new_focus, self.FOCUS_LOWER_BOUND, self.FOCUS_UPPER_BOUND)
            self.new_focus = round(self.new_focus)

            self.focus_history = np.append(self.focus_history, [self.new_focus])
            mirror_values[0] = self.new_focus

        if np.abs(self.second_dispersion_learning_rate * derivatives["second_dispersion"]) > 1:

            self.new_second_dispersion = (self.second_dispersion_history[-1] + (self.momentum*(self.second_dispersion_history[-1]-self.second_dispersion_history[-2])) - self.second_dispersion_learning_rate*self.second_dispersion_der_history[-1])
                                                       
            self.new_second_dispersion = np.clip(self.new_second_dispersion, self.SECOND_DISPERSION_LOWER_BOUND, self.SECOND_DISPERSION_UPPER_BOUND)
            self.new_second_dispersion = round(self.new_second_dispersion)

            self.second_dispersion_history = np.append(self.second_dispersion_history, [self.new_second_dispersion])
            dispersion_values[0] = self.new_second_dispersion

        if np.abs(self.third_dispersion_learning_rate * derivatives["third_dispersion"]) > 1:
            self.new_third_dispersion = (self.third_dispersion_history[-1] + (self.momentum*(self.third_dispersion_history[-1]-self.third_dispersion_history[-2])) - self.third_dispersion_learning_rate*self.third_dispersion_der_history[-1])

            self.new_third_dispersion = np.clip(self.new_third_dispersion, self.THIRD_DISPERSION_LOWER_BOUND, self.THIRD_DISPERSION_UPPER_BOUND)
            self.new_third_dispersion = round(self.new_third_dispersion)

            self.third_dispersion_history = np.append(self.third_dispersion_history, [self.new_third_dispersion])
            dispersion_values[1] = self.new_third_dispersion
        
        # if the change in all variables is less than one (we can not take smaller steps thus this is the optimization boundry)
        if (
            np.abs(self.third_dispersion_learning_rate * derivatives["third_dispersion"]) < 1 and
            np.abs(self.second_dispersion_learning_rate * derivatives["second_dispersion"]) < 1 and
            np.abs(self.focus_learning_rate * derivatives["focus"]) < 1
        ):
            print("Convergence achieved")
            
        # stop optimizing parameter if we reached optimization resolution limit
        
        elif np.abs(self.third_dispersion_learning_rate * derivatives["third_dispersion"]) < 1:
            print("Convergence achieved in third dispersion")
        
        elif np.abs(self.second_dispersion_learning_rate * derivatives["second_dispersion"]) < 1:
            print("Convergence achieved in second dispersion")
            
        elif np.abs(self.focus_learning_rate * derivatives["focus"]) < 1:
            print("Convergence achieved in focus")
        
        # if the count is not changing much this means that we are near the peak 
        if np.abs(self.count_history[-1] - self.count_history[-2]) <= self.count_change_count_change_tolerance:
            print("Convergence achieved")

    def process_images(self, new_images):
        self.initialize_image_files() 
        new_images = [image_path for image_path in new_images if os.path.exists(image_path)]
        new_images.sort(key=os.path.getctime)

        for image_path in new_images:
            self.img_mean_count = self.calc_count_per_image(image_path)
            self.image_group_count_sum += np.sum(self.img_mean_count)

            # keep track of the times the program ran (number of images we processed)
            self.images_processed += 1

            # conditional to check if the desired numbers of images to mean was processed
            if self.images_processed % self.image_group == 0:
                # take the mean count for the number of images set
                self.mean_count_per_image_group = np.mean(self.img_mean_count)
                # append to count_history list to keep track of count through the optimization process
                self.count_history = np.append(self.count_history, [self.mean_count_per_image_group])
                
                # update count for 'images_group' processed (number of image groups processed)
                self.image_groups_processed += 1
                self.iteration_data = np.append(self.iteration_data, [self.image_groups_processed])

                # if we are in the first time where the algorithm needs to adjust the value
                if self.image_groups_processed == 1:
                    print('-------------')   
                    
                    # add initial values to lists
                    self.focus_history = np.append(self.focus_history, [self.initial_focus])
                    self.second_dispersion_history = np.append(self.second_dispersion_history, [self.initial_second_dispersion])                   
                    self.third_dispersion_history = np.append(self.third_dispersion_history, [self.initial_third_dispersion])
                    
                    # print to help track the evolution of the system
                    print(f"initial values are: focus {self.focus_history[-1]}, second_dispersion {self.second_dispersion_history[-1]}, third_dispersion {self.third_dispersion_history[-1]}")
                    print(f"initial directions are: focus {self.random_direction[0]}, second_dispersion {self.random_direction[1]}, third_dispersion {self.random_direction[2]}")
                    
                    # call function to take random directions
                    self.initial_optimize()

                else:
                    self.image_groups_dir_run_count += 1
                    self.optimize_count()
        
                # adjust the values to the clipped bounderies 
                self.new_focus = round(np.clip(self.focus_history[-1], self.FOCUS_LOWER_BOUND, self.FOCUS_UPPER_BOUND))
                self.new_second_dispersion = round(np.clip(self.second_dispersion_history[-1], self.SECOND_DISPERSION_LOWER_BOUND, self.SECOND_DISPERSION_UPPER_BOUND))
                self.new_third_dispersion = round(np.clip(self.third_dispersion_history[-1], self.THIRD_DISPERSION_LOWER_BOUND, self.THIRD_DISPERSION_UPPER_BOUND))
                
                # update the plots
                self.plot_reset() # update plotting lists and reset variables

                # print the latest mean count (helps track system)
                print(f"Mean count for last {self.image_group} images: {self.count_history[-1]:.2f}")

                # print the current parameter values which resulted in the brightness above
                print(f"Current values are: focus {self.focus_history[-1]}, second_dispersion {self.second_dispersion_history[-1]}, third_dispersion {self.third_dispersion_history[-1]}")
                
                print('-------------')

if __name__ == "__main__":
    app = BetatronApplication([])
    
    # 100 iterations for algorithm
    for _ in range(100):
        app.process_images()

    win = QtWidgets.QMainWindow()
    sys.exit(app.exec_())