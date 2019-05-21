from fedem.fedemdll.vpmSolverRun import VpmSolverRun
import socket
import numpy as np
from scipy import signal
import struct

# Configure UDP Socket
PHYSICAL_TWIN_ADDRESS = ("0.0.0.0", 7331)

WEB_SERVER_ADDRESS = ("localhost", 8001)#"129.241.90.187", 8001)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(PHYSICAL_TWIN_ADDRESS)

def goToInitial(actuatorLowerInit, actuatorUpperInit):
    # Taken from Model
    actuatorUpperModel = 0.040999981 # Prismatic joint 3
    actuatorLowerModel = 0.10099981  # Prismatic joint 1

    # Timing
    duration = 5  # SECONDS
    timeStep = 0.01
    numberOfSteps = round((duration/timeStep))

    # STEPS
    actuatorLower = 0
    actuatorUpper = 0

    # Interpolation
    stepUpper = (actuatorUpperInit - actuatorUpperModel) / numberOfSteps
    stepLower = (actuatorLowerInit - actuatorLowerModel) / numberOfSteps

    hei = True
    # Go to initial
    for i in range(0, numberOfSteps, 1):
        time = twin.getCurrentTime()
        twin.setExtFunc(1, time, actuatorLower)
        twin.setExtFunc(2, time, actuatorUpper)
        twin.solveNext()

        # Get transformation data for all triads and parts

        transformationData = twin.save_transformation_state()
        sock.sendto(transformationData, WEB_SERVER_ADDRESS)


        actuatorLower = actuatorLower + stepLower
        actuatorUpper = actuatorUpper + stepUpper

    # One Second of Idle time
    for i in range(0, 100, 1):
        time = twin.getCurrentTime()
        twin.setExtFunc(1, time, actuatorLower)
        twin.setExtFunc(2, time, actuatorUpper)
        twin.solveNext()

        # Get transformation data for all triads and parts
        transformationData = twin.save_transformation_state()
        sock.sendto(transformationData, WEB_SERVER_ADDRESS)

# Open file with sensor data
with open('C:\\Users\\chris\\Documents\\FedemProsjekt\\DT_EXAMPLE\\CraneRun\\Good_New\\Apply2.txt', 'r') as file:
    lines = file.readlines()

# Remove lines of meta-data
lines = lines[39:(len(lines)-1)]

# DT setup parameters
fedem_model_path = 'CraneShort.fmm'

# Declare variables
unfiltered_UT = []
unfiltered_UR = []
unfiltered_UL = []
unfiltered_REF = []


# FILTERING
for i in range(len(lines)):

    # Get sensor data
    line = lines[i]
    temp = line.split('\t')
    REF = float(temp[1]) * 10.0 ** -6
    UR = float(temp[2]) * 10.0 ** -6
    UL = float(temp[3]) * 10.0 ** -6
    UT = float(temp[4]) * 10.0 ** -6
    TempComp = float(temp[11]) * 10.0 ** -6

    # Temperature compensation
    REF = REF - TempComp
    UR = UR - TempComp
    UL = UL - TempComp
    UT = UT - TempComp

    # Fill Arrays
    unfiltered_UT.append(UT)
    unfiltered_UR.append(UR)
    unfiltered_UL.append(UL)
    unfiltered_REF.append(REF)


# Get filter parameters
filter_a, filter_b = signal.butter(8, 10/50)

# Filter signals (Low Pass (Butterworth), Cutt-Off: 10Hz, Order: 8)
filtered_UT = signal.filtfilt(filter_a, filter_b, unfiltered_UT)
filtered_UR = signal.filtfilt(filter_a, filter_b, unfiltered_UR)
filtered_UL = signal.filtfilt(filter_a, filter_b, unfiltered_UL)
filtered_REF = signal.filtfilt(filter_a, filter_b, unfiltered_REF)


# Initiate VpmSolverRun object
with VpmSolverRun(fedem_model_path) as twin:
    # Initialization of solver (Needed for fedem functions)

    for n in range(2):
        twin.solveNext()

    # Get initial values for goToInit()
    line = lines[0]
    temp = line.split('\t')
    actuatorLower = (float(temp[5]) / 100)   # Prismatic Joint 1
    actuatorUpper = (float(temp[6]) / 100)   # Prismatic Joint 3

    # ------------------------------- CALCULATE COMPLIANCE MATRIX START --------------------------------------
    # This part is only needed once, unless there is made structural changes to the Fedem model

    # Variable declarations
    out_def = [19, 20, 21]  # UT UR UL
    Sinv = np.zeros((3, 3))
    inp = 1                 # Input Force [N]
    inp_def = [6, 7, 8]     # Fx Fy Fz

    for j in range(3):

        # Variable declarations
        out = [np.inf, np.inf, np.inf]  # Strain Output (From virtual strain gauges)

        # Apply Force
        time = twin.getCurrentTime()
        twin.setExtFunc(inp_def[j], time, inp)

        # Let Structure settle after applying force
        for k in range(600):
            twin.solveNext()

        # Get values from virtual strain gauges
        out[0] = twin.getFunction(out_def[0])   # UT
        out[1] = twin.getFunction(out_def[1])   # UR
        # out[2] = twin.getFunction(out_def[2]) # Inverse method using "UL"
        out[2] = twin.getFunction(35)           # REF

        time = twin.getCurrentTime()
        Sinv[:, j] = np.array(out)

        # Cancel Force
        twin.setExtFunc(inp_def[j], time, 0)
        twin.solveNext()

        # Half second of idle time
        for k in range(50):
            twin.solveNext()

    # Calculate compliance matrix S
    S = np.linalg.inv(Sinv)
    print("S")
    print(S)

    # ------------------------------- CALCULATE COMPLIANCE MATRIX END --------------------------------------

    goToInitial(actuatorLower, actuatorUpper)

    for i in range(0, len(lines), 1):
        time = twin.getCurrentTime()


        # CALCULATE FORCES
        # F = S@np.array([filtered_UT[i], filtered_UR[i], filtered_UL[i]]) # Inverse method using "UL"
        F = S @ np.array([filtered_UT[i], filtered_UR[i], filtered_REF[i]])

        # SET FORCE
        twin.setExtFunc(6, time, F[0])
        twin.setExtFunc(7, time, F[1])
        twin.setExtFunc(8, time, F[2])

        # PLOTTING STRAINS (REFERENCES)
        twin.setExtFunc(9, time, unfiltered_UT[i])
        twin.setExtFunc(10, time, unfiltered_UR[i])
        twin.setExtFunc(11, time, unfiltered_UL[i])
        twin.setExtFunc(12, time, unfiltered_REF[i])

        # Get sensor data
        line = lines[i]
        temp = line.split('\t')

        # Calculate Movement
        actuatorLower = (float(temp[5]) / 100) - 0.10099981     # Prismatic Joint 1
        actuatorUpper = (float(temp[6]) / 100) - 0.040999981    # Prismatic Joint 3
        base = float(temp[10]) * (3.14 / 180) * (10 / 16500)    # Radians

        # Actuator movement
        twin.setExtFunc(1, time, actuatorLower)
        twin.setExtFunc(2, time, actuatorUpper)

        # Plotting Actuator movement (REFERENCE)
        twin.setExtFunc(3, time, actuatorLower + 0.10099981)
        twin.setExtFunc(4, time, actuatorUpper + 0.040999981)

        # Base Rotation
        twin.setExtFunc(5, time, base)

        twin.solveNext()

        # Get transformation data for all triads and parts
        transformationData = twin.save_transformation_state()
        sock.sendto(transformationData, WEB_SERVER_ADDRESS)


