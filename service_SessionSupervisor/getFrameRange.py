import bpy

# Get the last frame of the current scene
last_frame = bpy.context.scene.frame_end
first_frame = bpy.context.scene.frame_start

# print(last_frame)
# print(first_frame)

print(f"FF:{first_frame}")
print(f"LF:{last_frame}")
