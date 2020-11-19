# RetopoFlow Warnings 

RetopoFlow might present a warning if it detects a situation which is not ideal to start in. 


## Layout: Quad View / Multiple 3D Views

RetopoFlow is designed to work in a single 3D view.
Running RetopoFlow with Quad View turned on or with multiple 3D Views can result in RetopoFlow showing up in every 3D View, but only allowing interaction in one.


## Auto Save / Save
If Blender's auto save is disabled, any work done since the last time you saved can be lost if Blender crashes. To enable auto save, go Edit > Preferences > Save & Load > Auto Save.

If you are working on an unsaved blend file, your changes will be saved to {options.get_auto_save_filepath()} when you press {{blender save}}.


## Performance: Target/Sources Too Large

RetopoFlow is designed to perform well on _typical_ production retopology scenarios.
Running RetopoFlow on source/target meshes beyond a reasonable range is possible, but it will result in slower performance and a poorer experience.

A typical retopology workflow would involve <{[warning max sources]} polygons in total for all source meshes and <{[warning max target]} polygons for the target mesh. That's the point at which Blender starts to slow down, and there's not a lot we can do to be faster than Blender itself. 

If your retopology target polygon count exceeds the {[warning max target]} count threshold, please try the following:

- Capture the surface details using a normal or a bump map instead of through geometry
- Use a Subdivision Surface modifier to smooth the mesh rather than additional edge loops
- Use the Mirror modifier and only retopologize half of the source

If your total source mesh(es) polygon count exceeds the {[warning max sources]} count threshold, try the following:

- Use a Decimate or Remesh modifier to reduce the overall count. 
- Create a decimated copy of your source mesh and retopologize the copy. As long as it doesn't noticibly impact the silhouette of the object, decimation won't affect the resulting retopology at all
- Disable any Subdivision Surface modifiers or lower the Multiresolution Modifier display level
- Segment your sources into separate parts and retopologize one at a time


## Layout: Quad View / Multiple 3D Views

RetopoFlow is designed to work in a single 3D view.
Running RetopoFlow with Quad View turned on or with multiple 3D Views can result in RetopoFlow showing up in every 3D View, but only allowing interaction in one.


## Auto Save / Save

If Blender's auto save is disabled, any work done since the last time you saved can be lost if Blender crashes.
To enable auto save, go Edit > Preferences > Save & Load > Auto Save.

If you are working on an _unsaved_ blend file, your changes will be saved to `{`options.get_auto_save_filepath()`}` when you press {{blender save}}.
