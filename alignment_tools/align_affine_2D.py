from PyQt5.QtWidgets import QWidget, QLabel, QGroupBox, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from numpy.typing import NDArray
import numpy as np
from qt_widgets import NDarray_to_QPixmap, LabeledDoubleSpinBox, LabeledSliderDoubleSpinBox, LabeledSliderSpinBox
from image_tools import im2single, im2uint8
import pyqtgraph as pg
import cv2

# https://github.com/pyqtgraph/pyqtgraph/blob/master/pyqtgraph/examples

# TODO: this probably belongs in image tools
class ImageControl(QWidget):
    '''
    Contains an image and controls the histogram
    Note that some operations are non-linear (e.g clipping or gamma),
    which means the order in which operations are applied matters.
    The order is the order of the widgets top->down.
    '''

    # TODO be able to reorganize widgets vertically to change the order of operations ?
    # TODO c&b and min/max not independent, change them concurently

    def __init__(self, image: NDArray, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.set_image(image)

        self.state = {
            'contrast': [1.0 for i in range(self.num_channels)],
            'brightness': [0.0 for i in range(self.num_channels)],
            'gamma': [1.0 for i in range(self.num_channels)],
            'min': [0.0 for i in range(self.num_channels)],
            'max': [1.0 for i in range(self.num_channels)]
        }
        
        self.create_components()
        self.layout_components()
        self.setMaximumWidth(image.shape[1])

        # setup zoom and pan
        self.zoom = 1.0
        self.last_mouse_pos = QPoint(0,0)
        self.im_height = self.image.shape[0]
        self.im_width = self.image.shape[1]
        self.bottomleft = QPoint(0,0)
        self.topright = QPoint(self.im_height,self.im_width)
        self.center = QPoint(self.im_height//2,self.im_width//2)
        
        # update 
        self.update_histogram()

    def set_image(self, image: NDArray):

        if len(image.shape) > 3:
            raise ValueError('Cannot deal with more than 3 dimensions')
        
        self.num_channels = 1 if len(image.shape) == 2 else image.shape[2]
        if self.num_channels == 1:
            image = image[:,:,np.newaxis]

        self.image = im2single(image)
        self.image_transformed = self.image.copy() 

    def create_components(self):

        ## image -------------------------------------------------
        self.image_label = QLabel(self)
        self.image_label.setPixmap(NDarray_to_QPixmap(im2uint8(self.image_transformed)))
        self.image_label.wheelEvent = self.on_mouse_wheel
        self.image_label.mouseMoveEvent = self.on_mouse_move

        ## controls ----------------------------------------------

        # expert mode
        self.expert = QCheckBox(self)
        self.expert.setText('expert mode')
        self.expert.stateChanged.connect(self.expert_mode)

        # channel: which image channel to act on
        self.channel = LabeledSliderSpinBox(self)
        self.channel.setText('channel')
        self.channel.setRange(0,self.num_channels-1)
        self.channel.setValue(0)
        self.channel.valueChanged.connect(self.change_channel)

        # contrast
        self.contrast = LabeledSliderDoubleSpinBox(self)
        self.contrast.setText('contrast')
        self.contrast.setRange(0,10)
        self.contrast.setValue(1.0)
        self.contrast.setSingleStep(0.05)
        self.contrast.valueChanged.connect(self.change_contrast)

        # brightness
        self.brightness = LabeledSliderDoubleSpinBox(self)
        self.brightness.setText('brightness')
        self.brightness.setRange(-1,1)
        self.brightness.setValue(0.0)
        self.brightness.setSingleStep(0.05)
        self.brightness.valueChanged.connect(self.change_brightness)

        # gamma
        self.gamma = LabeledSliderDoubleSpinBox(self)
        self.gamma.setText('gamma')
        self.gamma.setRange(0,10)
        self.gamma.setValue(1.0)
        self.gamma.setSingleStep(0.05)
        self.gamma.valueChanged.connect(self.change_gamma)

        # min
        self.min = LabeledSliderDoubleSpinBox(self)
        self.min.setText('min')
        self.min.setRange(0,1)
        self.min.setValue(0.0)
        self.min.setSingleStep(0.05)
        self.min.valueChanged.connect(self.change_min)

        # max
        self.max = LabeledSliderDoubleSpinBox(self)
        self.max.setText('max')
        self.max.setRange(0,1)
        self.max.setValue(1.0)
        self.max.setSingleStep(0.05)
        self.max.valueChanged.connect(self.change_max)

        ## histogram and curve: total transformation applied to pixel values -------
        self.curve = pg.plot()
        self.curve.setFixedHeight(100)
        self.curve.setYRange(0,1)
        self.histogram = pg.plot()
        self.histogram.setFixedHeight(150)

        ## auto: make the histogram flat 
        self.auto = QPushButton(self)
        self.auto.setText('Auto')
        self.auto.clicked.connect(self.auto_scale)

        ## reset: back to original histogram
        self.reset = QPushButton(self)
        self.reset.setText('Reset')
        self.reset.clicked.connect(self.reset_transform)

        self.curve.hide()
        self.histogram.hide()

    def layout_components(self):

        layout_buttons = QHBoxLayout()
        layout_buttons.addStretch()
        layout_buttons.addWidget(self.auto)
        layout_buttons.addWidget(self.reset)
        layout_buttons.addStretch()

        layout_main = QVBoxLayout(self)
        layout_main.addStretch()
        layout_main.addWidget(self.image_label)
        layout_main.addWidget(self.expert)
        layout_main.addWidget(self.channel)
        layout_main.addWidget(self.min)
        layout_main.addWidget(self.max)
        layout_main.addWidget(self.gamma)
        layout_main.addWidget(self.contrast)
        layout_main.addWidget(self.brightness)
        layout_main.addWidget(self.curve)
        layout_main.addWidget(self.histogram)
        layout_main.addLayout(layout_buttons)
        layout_main.addStretch()

    def change_channel(self):

        # restore channel state 
        w = self.channel.value()
        self.contrast.setValue(self.state['contrast'][w])
        self.brightness.setValue(self.state['brightness'][w])
        self.gamma.setValue(self.state['gamma'][w])
        self.min.setValue(self.state['min'][w])
        self.max.setValue(self.state['max'][w])

        self.update_histogram()

    def change_brightness(self):
        self.update_histogram()

    def change_contrast(self):
        self.update_histogram()

    def change_gamma(self):
        self.update_histogram()

    def change_min(self):

        w = self.channel.value()
        m = self.min.value() 
        M = self.max.value()

        # if min >= max restore old value 
        if m >= M:
            self.min.setValue(self.state['min'][w])
            
        self.update_histogram()

    def change_max(self):

        w = self.channel.value()
        m = self.min.value() 
        M = self.max.value()

        # if min >= max restore old value 
        if m >= M:
            self.max.setValue(self.state['max'][w])
    
        self.update_histogram()

    def update_histogram(self):
    
        # get parameters
        w = self.channel.value()
        c = self.contrast.value()
        b = self.brightness.value()
        g = self.gamma.value()
        m = self.min.value()
        M = self.max.value()

        # update parameter state 
        self.state['contrast'][w] = c
        self.state['brightness'][w] = b
        self.state['gamma'][w] = g
        self.state['min'][w] = m
        self.state['max'][w] = M

        # pan and zoom
        image_cropped = self.image[self.bottomleft.y():self.topright.y(), self.bottomleft.x():self.topright.x(),:]
        self.image_transformed = cv2.resize(image_cropped, None, fx=self.zoom, fy=self.zoom)
        if self.num_channels == 1:
            self.image_transformed = self.image_transformed[:,:,np.newaxis]

        self.curve.clear()
        self.histogram.clear()

        # TODO: this is a bit slow (histogram update in particular). Parallelize ? Do that on cropped image before resizing ?
        # reapply transformation on all channels
        for ch in range(self.num_channels):

            # transfrom image channel
            I = self.image_transformed[:,:,ch].copy()

            I = np.piecewise(
                I, 
                [I<self.state['min'][ch], (I>=self.state['min'][ch]) & (I<=self.state['max'][ch]), I>self.state['max'][ch]],
                [0, lambda x: (x-self.state['min'][ch])/(self.state['max'][ch]-self.state['min'][ch]), 1]
            )
            
            I = np.clip(self.state['contrast'][ch] * (I** self.state['gamma'][ch] -0.5) + self.state['brightness'][ch] + 0.5, 0 ,1)

            self.image_transformed[:,:,ch] = I

            if self.expert.isChecked():
                
                # update curves
                x = np.arange(0,1,0.02)
                u = np.piecewise(
                    x, 
                    [x<self.state['min'][ch], (x>=self.state['min'][ch]) & (x<=self.state['max'][ch]), x>self.state['max'][ch]],
                    [0, lambda x: (x-self.state['min'][ch])/(self.state['max'][ch]-self.state['min'][ch]), 1]
                )
                y = np.clip(self.state['contrast'][ch] * (u** self.state['gamma'][ch] -0.5) + self.state['brightness'][ch] + 0.5, 0 ,1)
                self.curve.plot(x,y,pen=(ch,3))

                # update histogram (slow)
                for ch in range(self.num_channels):
                    y, x = np.histogram(I.ravel(), x)
                    self.histogram.plot(x,y,stepMode="center", pen=(ch,3))

        # update image
        self.image_label.setPixmap(NDarray_to_QPixmap(im2uint8(self.image_transformed)))

    def on_mouse_wheel(self, event):
        # zoom on wheel scroll

        # get zoom 
        delta = event.angleDelta().y()
        self.zoom = max(self.zoom + 0.10*(delta and delta // abs(delta)), 1.0)
        
        # compute ROI to zoom around current ROI center
        h, w = self.im_height*self.zoom, self.im_width*self.zoom
        left = np.clip(int(self.center.x()*self.zoom - self.im_width/2), 0, w - self.im_width)
        right = left + self.im_width
        bottom = np.clip(int(self.center.y()*self.zoom - self.im_height/2), 0, h - self.im_height)
        top = bottom + self.im_height

        # store ROI
        self.bottomleft = QPoint(left, bottom)/self.zoom
        self.topright = QPoint(right, top)/self.zoom
        self.center = QPoint((left+right)/2, (bottom+top)/2)/self.zoom

        # update image
        self.update_histogram()

    def on_mouse_move(self, event):
        # pan on right mouse click

        if event.buttons() == Qt.RightButton:

            pos = event.pos()
            
            # pan on edges
            x, y = pos.x(), pos.y()
            dx, dy = 0,0
            if x < 0.05*self.im_width:
                dx += -10
                local_coord = QPoint(0.05*self.im_width, y)
                global_coord = self.image_label.mapToGlobal(local_coord)
                self.cursor().setPos(global_coord)
            elif x > 0.9*self.im_width:
                dx += 10
                local_coord = QPoint(0.9*self.im_width, y)
                global_coord = self.image_label.mapToGlobal(local_coord)
                self.cursor().setPos(global_coord)
            if y < 0.05*self.im_height:
                dy += -10
                local_coord = QPoint(x, 0.05*self.im_height)
                global_coord = self.image_label.mapToGlobal(local_coord)
                self.cursor().setPos(global_coord)
            elif y > 0.9*self.im_height:
                dy += 10
                local_coord = QPoint(x, 0.9*self.im_height)
                global_coord = self.image_label.mapToGlobal(local_coord)
                self.cursor().setPos(global_coord)
        
            # compute ROI 
            h, w = self.im_height*self.zoom, self.im_width*self.zoom
            left = np.clip(int(self.bottomleft.x()*self.zoom + dx), 0, w - self.im_width)
            right = left + self.im_width
            bottom = np.clip(int(self.bottomleft.y()*self.zoom + dy), 0, h - self.im_height)
            top = bottom + self.im_height

            # store ROI
            self.bottomleft = QPoint(left, bottom)/self.zoom
            self.topright = QPoint(right, top)/self.zoom
            self.center = QPoint((left+right)/2, (bottom+top)/2)/self.zoom

            # update image
            self.update_histogram()

    def auto_scale(self):

        m = np.percentile(self.image, 5)
        M = np.percentile(self.image, 99)
        self.min.setValue(m)
        self.max.setValue(M)
        self.update_histogram()
        self.image_label.setPixmap(NDarray_to_QPixmap(im2uint8(self.image_transformed)))
    
    def reset_transform(self):
        
        # reset state
        self.state = {
            'contrast': [1.0 for i in range(self.num_channels)],
            'brightness': [0.0 for i in range(self.num_channels)],
            'gamma': [1.0 for i in range(self.num_channels)],
            'min': [0.0 for i in range(self.num_channels)],
            'max': [1.0 for i in range(self.num_channels)]
        }
                
        # reset parameters
        self.contrast.setValue(1.0)
        self.brightness.setValue(0.0)
        self.gamma.setValue(1.0)
        self.min.setValue(0.0)
        self.max.setValue(1.0)

        # reset image
        self.image_transformed = self.image.copy()
        self.image_label.setPixmap(NDarray_to_QPixmap(im2uint8(self.image_transformed)))
        self.update_histogram()

    def expert_mode(self):

        if self.expert.isChecked():
            self.curve.show()
            self.histogram.show()
        else:
            self.curve.hide()
            self.histogram.hide()

        self.update_histogram()

def l2(p: QPoint)-> float :
    return np.sqrt(p.x()**2 + p.y()**2)

class ImageControlCP(ImageControl):

    def __init__(self, image: NDArray, *args, **kwargs):
        
        super().__init__(image, *args, **kwargs)
        self.control_points = []
        self.image_label.mousePressEvent = self.on_mouse_press
        
    def paintEvent(self, event):

        # redraw over image
        painter = QPainter(self.image_label.pixmap())
        pen = QPen()
        pen.setWidth(3)
        font = QFont()
        font.setPixelSize(30)
        pen_color = QColor(255, 0, 0, 255)
        pen.setColor(pen_color)
        painter.setPen(pen)
        painter.setFont(font)
        offset = QPoint(5,-5)
        for cp in self.control_points:
            painter.drawPoint((cp[0]-self.bottomleft)*self.zoom)
            painter.drawText((cp[0]+offset-self.bottomleft)*self.zoom, str(cp[1]))
        
    def on_mouse_press(self, event):
        
        # left-click adds a new control point
        if event.button() == Qt.LeftButton:
            
            # remove point with shift pressed
            if event.modifiers() == Qt.ShiftModifier:
                # get closest point and delete from list of points
                distances = [l2(event.pos() - pos) for (pos, name) in self.control_points]
                if distances:
                    closest_point = np.argmin(distances)
                    self.control_points.pop(closest_point)

            # add point otherwise
            else:
                num = 0 if not self.control_points else max(self.control_points, key=lambda x: x[1])[1] + 1
                pos = event.pos()/self.zoom + self.bottomleft 
                self.control_points.append((pos, num))
            
        self.update_histogram()
        self.update()

class AlignAffine2D(QWidget):
    def __init__(self, fixed: NDArray, moving: NDArray, *args, **kwargs) -> None:
        
        super().__init__(*args, **kwargs)

        self.moving = moving
        self.fixed = fixed
        self.moving_transformed = self.moving
        self.overlay = np.dstack((self.fixed,self.moving_transformed,np.zeros_like(self.fixed)))
        self.create_components()
        self.layout_components()

    def create_components(self):

        ## images

        self.moving_label = ImageControlCP(self.moving)
        self.fixed_label = ImageControlCP(self.fixed)
        self.overlay_label = ImageControl(self.overlay)
    
        ## 2D affine transform parameters

        self.scale_x = LabeledDoubleSpinBox(self)
        self.scale_x.setText('scale x')
        self.scale_x.setRange(-1000,1000)
        self.scale_x.setValue(1.0)
        self.scale_x.setSingleStep(0.05)
        self.scale_x.valueChanged.connect(self.update_transformation)

        self.scale_y = LabeledDoubleSpinBox(self)
        self.scale_y.setText('scale y')
        self.scale_y.setRange(-1000,1000)
        self.scale_y.setValue(1.0)
        self.scale_y.setSingleStep(0.05)
        self.scale_y.valueChanged.connect(self.update_transformation)

        self.shear_x = LabeledDoubleSpinBox(self)
        self.shear_x.setText('shear x')
        self.shear_x.setRange(-1000,1000)
        self.shear_x.setValue(0.0)
        self.shear_x.setSingleStep(0.01)
        self.shear_x.valueChanged.connect(self.update_transformation)

        self.shear_y = LabeledDoubleSpinBox(self)
        self.shear_y.setText('shear y')
        self.shear_y.setRange(-1000,1000)
        self.shear_y.setValue(0.0)
        self.shear_y.setSingleStep(0.01)
        self.shear_y.valueChanged.connect(self.update_transformation)

        self.rotation = LabeledDoubleSpinBox(self)
        self.rotation.setText('rotate (deg)')
        self.rotation.setRange(-100_000,100_000)
        self.rotation.setValue(0)
        self.rotation.setSingleStep(0.5)
        self.rotation.valueChanged.connect(self.update_transformation)

        self.translate_x = LabeledDoubleSpinBox(self)
        self.translate_x.setText('translate x')
        self.translate_x.setRange(-100_000,100_000)
        self.translate_x.setValue(0.0)
        self.translate_x.setSingleStep(1.0)
        self.translate_x.valueChanged.connect(self.update_transformation)

        self.translate_y = LabeledDoubleSpinBox(self)
        self.translate_y.setText('translate y')
        self.translate_y.setRange(-100_000,100_000)
        self.translate_y.setValue(0.0)
        self.translate_y.setSingleStep(1.0)
        self.translate_y.valueChanged.connect(self.update_transformation)

        self.transformation_matrix_table = QTableWidget(self)
        self.transformation_matrix_table.setRowCount(3)
        self.transformation_matrix_table.setColumnCount(3)  
        self.transformation_matrix_table.setItem(0,0,QTableWidgetItem('1.0'))
        self.transformation_matrix_table.setItem(0,1,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(0,2,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(1,0,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(1,1,QTableWidgetItem('1.0'))
        self.transformation_matrix_table.setItem(1,2,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(2,0,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(2,1,QTableWidgetItem('0.0'))
        self.transformation_matrix_table.setItem(2,2,QTableWidgetItem('1.0'))
        self.transformation_matrix_table.cellEntered.connect(self.update_transformation_matrix)
        self.transformation_matrix_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.transformation_matrix_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.transformation_matrix_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transformation_matrix_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transformation_matrix_table.setMaximumHeight(100)


        self.transformation_groupbox = QGroupBox('Parameters:')
        
        self.transform = QWidget(self)

        self.align_cp = QPushButton(self)
        self.align_cp.setText('Align with control points')
        self.align_cp.clicked.connect(self.align_control_points)

        self.align_auto = QPushButton(self)
        self.align_auto.setText('Align automatically')
        self.align_auto.clicked.connect(self.align_automatically)

    def layout_components(self):
        
        layout_params = QVBoxLayout(self.transformation_groupbox)
        layout_params.addWidget(self.scale_x)
        layout_params.addWidget(self.scale_y)
        layout_params.addWidget(self.shear_x)
        layout_params.addWidget(self.shear_y)
        layout_params.addWidget(self.rotation)
        layout_params.addWidget(self.translate_x)
        layout_params.addWidget(self.translate_y)
        layout_params.addWidget(self.transformation_matrix_table)
        layout_params.addWidget(self.align_cp)
        layout_params.addWidget(self.align_auto)
        layout_params.addStretch()

        layout_fixed_moving = QHBoxLayout(self.transform)
        layout_fixed_moving.addStretch()
        layout_fixed_moving.addWidget(self.fixed_label)
        layout_fixed_moving.addWidget(self.moving_label)
        layout_fixed_moving.addStretch()

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.transform, "transform")
        self.tabs.addTab(self.overlay_label, "overlay")

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.transformation_groupbox)

    def update_overlay(self, T: NDArray):

        self.moving_transformed = cv2.warpAffine(self.moving, T[:2,:], self.fixed.shape)
        self.overlay = np.dstack((self.fixed,self.moving_transformed,np.zeros_like(self.fixed)))
        self.overlay_label.set_image(self.overlay)
        self.overlay_label.reset_transform()

    def update_transformation_matrix(self):
        pass

    def update_transformation(self):
        
        sh_x = self.shear_x.value()
        sh_y = self.shear_y.value()
        c = np.cos(np.deg2rad(self.rotation.value()))
        s = np.sin(np.deg2rad(self.rotation.value()))
        t_x = self.translate_x.value()
        t_y = self.translate_y.value()
        sc_x = self.scale_x.value()
        sc_y = self.scale_y.value()

        Shear = np.array([[ 1.0, sh_x,   0],
                          [sh_y,  1.0,   0],
                          [   0,    0, 1.0]])
        
        Rotation = np.array([[c, -s,   0],
                             [s,  c,   0],
                             [0,  0, 1.0]])
        
        Translation = np.array([[1.0,   0, t_x],
                                [0,   1.0, t_y],
                                [0,     0, 1.0]])
        
        Scale = np.array([[sc_x,    0,   0],
                          [0,    sc_y,   0],
                          [0,       0, 1.0]])

        T = Shear @ Scale @ Rotation @ Translation
        self.update_overlay(T)

    def align_control_points(self):

        a = [[pos.x(), pos.y(), 1] for pos, name in self.fixed_label.control_points]
        b = [[pos.x(), pos.y(), 1] for pos, name in self.moving_label.control_points]
        T = np.transpose(np.linalg.lstsq(a, b, rcond=None)[0])

        # TODO extract param value: this is a bit hard

        # update transformation matrix
        for i in range(3):
            for j in range(3):
                self.transformation_matrix_table.setItem(i,j,QTableWidgetItem(f'{T[i,j]:2f}'))

        self.update_overlay(T)

    def align_automatically(self):
        pass
