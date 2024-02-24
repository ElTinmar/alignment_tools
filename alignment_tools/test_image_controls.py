from alignment_tools.align_affine_2D import ImageControl
from PyQt5.QtWidgets import QApplication
import sys
import cv2

IMAGE = 'toy_data/image_00.jpg'

app = QApplication(sys.argv)
window = ImageControl(cv2.imread(IMAGE)[:,:,0])
window.show()
app.exec()
