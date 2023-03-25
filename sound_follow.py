import pyaudio as pa
import struct
import math
import time
from motor_control import VESC

# Find the index of each mic using 'python3 -m sounddevice' in the jetson's terminal
FRONT_MIC_INDEX = 12
LEFT_MIC_INDEX = 13
RIGHT_MIC_INDEX = 11

CHUNK_SIZE = 1024
RATE = 44100

VESC_PORT = "/dev/ttyACM0"

# Buffer to average the values of previous sound values to remove the impact of outlier noises. Each additional
# buffer increment increases the look-back by 0.2 seconds. If this value is too small, outliers will have a larger
# effect on the robot's movement. If this value is too big, the robot will take longer to adapt to changes
# in sound direction
BUFFER_SIZE = 6


# Helper function to calculate the decibel value of the given data stream using the root mean squared method
def get_decibel(data):
    data_count = len(data)/2
    format = "%dh"%(data_count)
    unpacked = struct.unpack(format,data)
    sum_squares = 0.0
    for entry in unpacked:
        n = entry * (1.0/32768)
        sum_squares += n*n
    rms = math.sqrt(sum_squares/data_count)
    return 20*math.log10(rms)

# Returns direction array [Left/Right, Front/Back] given the decibel values of each microphone. Need to implement threshold values to help
# the distinction between front and back directions
def find_direction(front, left, right):
    direction = [0,0]
    if(left > right):
        direction[0] = "Left"
    else:
        direction[0] = "Right"
    if(right > front and left > front):
        direction[1] = "Back"
    else:
        direction[1] = "Front" 
    return direction


pyA = pa.PyAudio()
stream_front = pyA.open(format = pa.paInt16,
        input_device_index = FRONT_MIC_INDEX,
        channels = 1,
        rate = RATE,
        input = True,
        frames_per_buffer = CHUNK_SIZE)

stream_left = pyA.open(format = pa.paInt16,
        input_device_index = LEFT_MIC_INDEX,
        channels = 1,
        rate = RATE,
        input = True,
        frames_per_buffer = CHUNK_SIZE)

stream_right = pyA.open(format = pa.paInt16,
        input_device_index = RIGHT_MIC_INDEX,
        channels = 1,
        rate = RATE,
        input = True,
        frames_per_buffer = CHUNK_SIZE)

# These are the buffer used to remove the impact of outlier sound values
front_vals = []
left_vals = []
right_vals = []
prev_front = []
vesc = VESC(VESC_PORT)
vesc.turn(0)
skip_index = 0

# Currently robot will keep moving towards audio source, can implement stop once noise reaches a set threshold
while(True):

    # Tick rate is 0.2 seconds
    time.sleep(0.2)

    # Collect decibel values of current tick and add to buffers
    data_front = stream_front.read(CHUNK_SIZE, exception_on_overflow = False)
    data_left = stream_left.read(CHUNK_SIZE, exception_on_overflow = False)
    data_right = stream_right.read(CHUNK_SIZE, exception_on_overflow = False)
    front_val = get_decibel(data_front) 
    left_val = get_decibel(data_left) 
    right_val = get_decibel(data_right) 
    front_vals.append(front_val)
    left_vals.append(left_val)
    right_vals.append(right_val)

    # prev_front holds the front values from 0.6 seconds ago. Used to tell if robot is heading towards/away source of sound
    if(len(front_vals) >= 3 and len(front_vals) != BUFFER_SIZE):
        prev_front.append(front_vals[skip_index])
        skip_index += 1
    if(len(front_vals) == BUFFER_SIZE):
        prev_front.append(front_vals[0])
        front_vals.pop(0)
        left_vals.pop(0)
        right_vals.pop(0)
    if(len(prev_front) == BUFFER_SIZE):
        prev_front.pop(0)
    
    direction_array = find_direction(sum(front_vals), sum(left_vals), sum(right_vals))

    # Uncomment to print direction values for debugging
    # print("----------------------")
    # print('Direction: ', direction_array)
    # print("Front Decibel: ", sum(front_vals))
    # print("Prev Front Decibel: ", sum(prev_front))
    # print("Left Decibel: ", sum(left_vals))
    # print("Right Decibel: ", sum(right_vals))
    # print("----------------------")

    # Move car using VESC class
    # Adding to prev_front to ensure robot is heading in correct direction before straightening wheels
    if(sum(front_vals) > sum(prev_front) + 30):
        vesc.turn(0)
        time.sleep(0.2)
    elif(direction_array[0] == "Left"):
        vesc.turn(-50)
        time.sleep(0.2)
    else:
        vesc.turn(50)
        time.sleep(0.2)
    if(direction_array[1] == "Back"):
        vesc.set_speed(-0.15)
    else:
        vesc.set_speed(0.15)