# Saving the new hash is enough: the post_save signal revokes every refresh token of the user.
def set_new_password(user, new_password):
    user.set_password(new_password)
    user.save(update_fields=["password"])
