# video_friendly_video_cropper
 Blender Addon that allows a user friendly way of cropping videos with render border

# Why
Video cropping doesn't have to be hard. But it is anyway.

This addon aims to provide a slightly easier way to just crop videos and as a bonus, create aPNGs out of them.

# How
In the shader graph editor,
* switch to World
* create a texture image node
* Connect the Window output of a TextureCoordinate node to the tex image node
* load your video in the tex image node
* draw a render border inside of camera view

This addon uses the camera's render border to crop the video
You can preview/export the crop in Properties > Output > Video Cropper Panel
You can change/enable the settings, but not all settings are supported for previewing, only for exporting.
* Colors Limit