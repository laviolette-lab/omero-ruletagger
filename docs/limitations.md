# Known Limitations
* Currently impossible to add arguments to the model walk
  * For example a you can't filter a condition to only check annotations in a certain namespace
  * This example could be fixed by comparing the 'ns' value against the desired value, but it still won't filter
* Regex rules can only be applied to Images currently.
* Cannot specify objects to operate on within the rules file.
  * Planned addition in schemav2 but wanted to get this out and get some feedback for schemav2
* Doesn't handle Annotations very well.
  * This is because the omero-py package doesn't have getters for specific annotation types
    * This causes AttributeErrors
  * Map and Table Annotations especially need extra thought to be able to meaningfully rule against
* Also doesn't handle properties
  * Due to the compilation process, we need getters to access properties
  * Could be possible to add with some lambda
    * Decided to leave as is for now because most properties have a getter (thanks java!)
* Pretty slow and inefficient
  * Makes more requests than it needs to
  * Causes it to take longer than it needs to
  * Decided to leave as is for readability sake
    * We run it once a night, could probably do it once a week
    * Both walking and recursion can get complex, tried my best to stay legible (unlike my first implementation)