# lxml

Test and show how the text property gets split and truncates text within an element if comments are embedded.

As documented in a Jupyter notebook, it shows that extending the lxml etree Element classes to have an all text method or property is not trivial and has undesirable side affects of injecting a parent node into the tree and pushing the element, attributes and properties of the instantiated/wrapped object as a child nodes.
