    <%doc>
        HTML Template for pdoc3 customized DevilDex
    </%doc>

    <%
      import os
      import pdoc
      from pdoc.html_helpers import extract_toc, glimpse, to_html as _to_html, format_git_link


      external_links = context.get('external_links', True)
      # link_prefix = context.get('link_prefix', '')
      show_inherited_members = context.get('show_inherited_members', False)
      docformat = context.get('docformat', 'markdown')
      latex_math = context.get('latex_math', False)
      show_source_code = context.get('show_source_code', True)
      git_link_template = context.get('git_link_template', None)
      sort_identifiers = context.get('sort_identifiers', True)
      show_type_annotations = context.get('show_type_annotations', True)
      http_server = context.get('http_server', False)
      extract_module_toc_into_sidebar = context.get('extract_module_toc_into_sidebar', True)
      list_class_variables_in_index = context.get('list_class_variables_in_index', True)
      google_search_query = context.get('google_search_query', '')
      lunr_search = context.get('lunr_search', None)
      html_lang = context.get('html_lang', 'en')

      def link(dobj: pdoc.Doc, name=None):
        name = name or dobj.qualname + ('()' if isinstance(dobj, pdoc.Function) else '')
        if isinstance(dobj, pdoc.External) and not external_links:
            return name
        url = dobj.url(relative_to=module, link_prefix=link_prefix,
                       top_ancestor=not show_inherited_members)
        return f'<a title="{dobj.refname}" href="{url}">{name}</a>'

      def to_html(text_input):
        return _to_html(text_input, docformat=docformat, module=module, link=link, latex_math=latex_math)

      def get_annotation(bound_method, sep=':'):
        annot = show_type_annotations and bound_method(link=link) or ''
        if annot:
            annot = ' ' + sep + '\N{NBSP}' + annot
        return annot
    %>

    <%def name="ident(name)"><span class="ident">${name}</span></%def>

    <%def name="show_source(d)">
      % if (show_source_code or git_link_template) and \
            not isinstance(d, pdoc.Module) and d.source and \
            d.obj is not getattr(d.inherits, 'obj', None):
        <% git_link = format_git_link(git_link_template, d) %>
        % if show_source_code:
          <details class="source">
            <summary>
                <span>Expand source code</span>
                % if git_link:
                  <a href="${git_link}" class="git-link" target="_blank">Browse git</a>
                %endif
            </summary>
            <pre><code>${d.source | h}</code></pre>
          </details>
        % elif git_link:
          <div class="git-link-div"><a href="${git_link}" class="git-link">Browse git</a></div>
        %endif
      %endif
    </%def>

    <%def name="show_desc(d, short=False)">
      <%
      inherits = ' inherited' if d.inherits else ''
      docstring = glimpse(d.docstring) if short or inherits else d.docstring
      %>
      % if d.inherits:
          <p class="inheritance">
              <em>Inherited from:</em>
              % if hasattr(d.inherits, 'cls'):
                  <code>${link(d.inherits.cls)}</code>.<code>${link(d.inherits, d.name)}</code>
              % else:
                  <code>${link(d.inherits)}</code>
              % endif
          </p>
      % endif
      % if not isinstance(d, pdoc.Module):
        ${show_source(d)}
      % endif
      <div class="desc${inherits}">${docstring | to_html}</div>
    </%def>

    <%def name="show_module_list(modules_list_param)">
        <h1>Python module list</h1>
        % if not modules_list_param:
          <p>No modules found.</p>
        % else:
          <dl id="http-server-module-list">
          % for name, desc in modules_list_param:
              <div class="flex">
              <dt><a href="${link_prefix}${name}">${name}</a></dt>
              <dd>${desc | glimpse, to_html}</dd>
              </div>
          % endfor
          </dl>
        % endif
    </%def>

    <%def name="show_column_list(items)">
      <%
          two_column = len(items) >= 6 and all(len(i.name) < 20 for i in items)
      %>
      <ul class="${'two-column' if two_column else ''}">
      % for item in items:
        <li><code>${link(item, item.name)}</code></li>
      % endfor
      </ul>
    </%def>

    <%def name="show_module(module_param)">
      <%
      variables = module_param.variables(sort=sort_identifiers)
      classes = module_param.classes(sort=sort_identifiers)
      functions = module_param.functions(sort=sort_identifiers)
      submodules = module_param.submodules()
      %>

      <%def name="show_func(f)">
        <dt id="${f.refname}"><code class="name flex">
            <%
                params_list = f.params(annotate=show_type_annotations, link=link)
                joined_params_for_len_check = ', '.join(params_list)
                sep = ',<br>' if len(joined_params_for_len_check) > 75 else ', '
                params_str = sep.join(params_list)
                return_type = get_annotation(f.return_annotation, '\N{non-breaking hyphen}>')
            %>
            <span>${f.funcdef()} ${ident(f.name)}</span>(<span>${params_str})${return_type}</span>
        </code></dt>
        <dd>${show_desc(f)}</dd>
      </%def>

      <header>
      % if http_server:
        <nav class="http-server-breadcrumbs">
          <a href="/">All packages</a>
          <% parts = module_param.name.split('.')[:-1] %>
          % for i, m_part in enumerate(parts):
            <% parent_module_name = '.'.join(parts[:i+1]) %>
            :: <a href="/${parent_module_name.replace('.', '/')}/">${parent_module_name}</a>
          % endfor
        </nav>
      % endif
      <h1 class="title">${'Namespace' if module_param.is_namespace else  \
                          'Package' if module_param.is_package and not module_param.supermodule else \
                          'Module'} <code>${module_param.name}</code></h1>
      </header>

      <section id="section-intro">
      ${module_param.docstring | to_html}
      </section>

      <section>
        % if submodules:
        <h2 class="section-title" id="header-submodules">Sub-modules</h2>
        <dl>
        % for m in submodules:
          <dt><code class="name">${link(m)}</code></dt>
          <dd>${show_desc(m, short=True)}</dd>
        % endfor
        </dl>
        % endif
      </section>

      <section>
        % if variables:
        <h2 class="section-title" id="header-variables">Global variables</h2>
        <dl>
        % for v in variables:
          <% var_return_type = get_annotation(v.type_annotation) %>
          <dt id="${v.refname}"><code class="name">var ${ident(v.name)}${var_return_type}</code></dt>
          <dd>${show_desc(v)}</dd>
        % endfor
        </dl>
        % endif
      </section>

      <section>
        % if functions:
        <h2 class="section-title" id="header-functions">Functions</h2>
        <dl>
        % for f_item in functions:
          ${show_func(f_item)}
        % endfor
        </dl>
        % endif
      </section>

      <section>
        % if classes:
        <h2 class="section-title" id="header-classes">Classes</h2>
        <dl>
        % for c in classes:
          <%
          class_vars = c.class_variables(show_inherited_members, sort=sort_identifiers)
          smethods = c.functions(show_inherited_members, sort=sort_identifiers) # Static methods in pdoc context
          inst_vars = c.instance_variables(show_inherited_members, sort=sort_identifiers)
          methods = c.methods(show_inherited_members, sort=sort_identifiers)
          mro = c.mro()
          subclasses_list = c.subclasses()
          class_params_list = c.params(annotate=show_type_annotations, link=link)
          joined_class_params_for_len_check = ', '.join(class_params_list)
          class_sep = ',<br>' if len(joined_class_params_for_len_check) > 75 else ', '
          class_params_str = class_sep.join(class_params_list)
          %>
          <dt id="${c.refname}"><code class="flex name class">
              <span>class ${ident(c.name)}</span>
              % if class_params_str:
                  <span>(</span><span>${class_params_str})</span>
              % endif
          </code></dt>

          <dd>${show_desc(c)}

          % if mro:
              <h3>Ancestors</h3>
              <ul class="hlist">
              % for cls_item in mro:
                  <li>${link(cls_item)}</li>
              % endfor
              </ul>
          %endif

          % if subclasses_list:
              <h3>Subclasses</h3>
              <ul class="hlist">
              % for sub_item in subclasses_list:
                  <li>${link(sub_item)}</li>
              % endfor
              </ul>
          % endif
          % if class_vars:
              <h3>Class variables</h3>
              <dl>
              % for v_item in class_vars:
                  <% cv_return_type = get_annotation(v_item.type_annotation) %>
                  <dt id="${v_item.refname}"><code class="name">var ${ident(v_item.name)}${cv_return_type}</code></dt>
                  <dd>${show_desc(v_item)}</dd>
              % endfor
              </dl>
          % endif
          % if smethods:
              <h3>Static methods</h3>
              <dl>
              % for f_item_static in smethods:
                  ${show_func(f_item_static)}
              % endfor
              </dl>
          % endif
          % if inst_vars:
              <h3>Instance variables</h3>
              <dl>
              % for v_item_inst in inst_vars:
                  <% iv_return_type = get_annotation(v_item_inst.type_annotation) %>
                  <dt id="${v_item_inst.refname}"><code class="name">${v_item_inst.kind} ${ident(v_item_inst.name)}${iv_return_type}</code></dt>
                  <dd>${show_desc(v_item_inst)}</dd>
              % endfor
              </dl>
          % endif
          % if methods:
              <h3>Methods</h3>
              <dl>
              % for f_item_method in methods:
                  ${show_func(f_item_method)}
              % endfor
              </dl>
          % endif

          % if not show_inherited_members:
              <%
                  inherited_members_list = c.inherited_members()
              %>
              % if inherited_members_list:
                  <h3>Inherited members</h3>
                  <ul class="hlist">
                  % for cls_item_inherited, mems_list in inherited_members_list:
                      <li><code><b>${link(cls_item_inherited)}</b></code>:
                          <ul class="hlist">
                              % for m_item_inherited in mems_list:
                                  <li><code>${link(m_item_inherited, name=m_item_inherited.name)}</code></li>
                              % endfor
                          </ul>
                      </li>
                  % endfor
                  </ul>
              % endif
          % endif
          </dd>
        % endfor
        </dl>
        % endif
      </section>
    </%def>

    <%def name="module_index(module_param)">
      <%
      idx_variables = module_param.variables(sort=sort_identifiers)
      idx_classes = module_param.classes(sort=sort_identifiers)
      idx_functions = module_param.functions(sort=sort_identifiers)
      idx_submodules = module_param.submodules()
      idx_supermodule = module_param.supermodule
      %>
      <nav id="sidebar" class="toc">
        <%include file="logo.mako"/>

        % if google_search_query:
            <div class="gcse-search" style="height: 70px"
                 data-as_oq="${' '.join(google_search_query.strip().split()) | h }"
                 data-gaCategoryParameter="${module_param.refname | h}">
            </div>
        % endif

        % if lunr_search is not None:
          <%include file="_lunr_search.inc.mako"/>
        % endif

        ${extract_toc(module_param.docstring) if extract_module_toc_into_sidebar else ''}
        <ul id="index">
        % if idx_supermodule:
        <li><h3>Super-module</h3>
          <ul>
            <li><code>${link(idx_supermodule)}</code></li>
          </ul>
        </li>
        % endif

        % if idx_submodules:
        <li><h3><a href="#header-submodules">Sub-modules</a></h3>
          <ul>
          % for m_idx in idx_submodules:
            <li><code>${link(m_idx)}</code></li>
          % endfor
          </ul>
        </li>
        % endif

        % if idx_variables:
        <li><h3><a href="#header-variables">Global variables</a></h3>
          ${show_column_list(idx_variables)}
        </li>
        % endif

        % if idx_functions:
        <li><h3><a href="#header-functions">Functions</a></h3>
          ${show_column_list(idx_functions)}
        </li>
        % endif

        % if idx_classes:
        <li><h3><a href="#header-classes">Classes</a></h3>
          <ul>
          % for c_idx in idx_classes:
            <li>
            <h4><code>${link(c_idx)}</code></h4>
            <%
                idx_members_list = c_idx.functions(sort=sort_identifiers) + c_idx.methods(sort=sort_identifiers)
                if list_class_variables_in_index:
                    idx_members_list += (c_idx.instance_variables(sort=sort_identifiers) +
                                c_idx.class_variables(sort=sort_identifiers))
                if not show_inherited_members:
                    idx_members_list = [i for i in idx_members_list if not i.inherits]
                if sort_identifiers:
                  idx_members_list = sorted(idx_members_list)
            %>
            % if idx_members_list:
              ${show_column_list(idx_members_list)}
            % endif
            </li>
          % endfor
          </ul>
        </li>
        % endif
        </ul>
      </nav>
    </%def>

    <!DOCTYPE html>
    <html lang="${html_lang}">
    <head>
        <%include file="head.mako"/>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark devildex-top-bar bg-dark sticky-top">
            <div class="container-fluid">
                                        <a class="navbar-brand d-flex align-items-center" id="navbar-brand" href="${module.url(relative_to=module, link_prefix=link_prefix) if module else '#'} ">

        <img src="${link_prefix}static/imgs/logo-final.png" alt="${module.name if module else 'Project'} Logo" class="me-2" height="80">
        <span>${module.name if module else 'Project'}</span>
    </a>


                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#devildexNavbarContent" aria-controls="devildexNavbarContent" aria-expanded="false" aria-label="Toggle navigation">
                  <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="devildexNavbarContent">
                  <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    <li class="nav-item">
                      <a class="nav-link active" aria-current="page" href="${module.url(relative_to=module, link_prefix=link_prefix) if module else '#'}">Module Home</a>
                    </li>
                  </ul>
                </div>
              </div>
        </nav>

        <main role="main" class="container-fluid mt-4 mb-4" id="main-content">
            <div class="row">
                <aside class="col-md-3" id="sidebar-nav">
                    <div class="position-sticky" style="top: 5rem;">
                        % if module:
                            <%include file="module_index.mako" />
                        % elif context.get('module_list') and context.get('modules'):
                            ${show_module_list(context.get('modules'))}
                        % else:
                            Index unavailable(module undefined and is not in module_list)
                        % endif
                    </div>
                </aside>

                <article class="col-md-9">
                    % if module:
                        ${show_module(module)}
                    % elif context.get('module_list') and context.get('modules'):
                        ${show_module_list(context.get('modules'))}
                    % else:
                        Module Content unavailable (module undefined and is not in module_list)
                    % endif
                </article>
            </div>
        </main>

        <footer class="footer mt-auto py-3 bg-dark text-light border-top" id="footer-info">
          <div class="container">
            <div class="row">
                <div class="col-12 text-center">
                    <small>
                        <%include file="credits.mako"/>
                        Generated by <a href="https://pdoc3.github.io/pdoc" title="pdoc: Python API documentation generator" class="text-light"><cite>pdoc</cite> ${pdoc.__version__ if 'pdoc' in globals() and hasattr(pdoc, '__version__') else 'N/A'}</a>.
                    </small>
                </div>
            </div>
          </div>
        </footer>

        <script src="static/bootstrap/js/bootstrap.bundle.min.js"></script>
        <script src="static/js/pdoc3_devildex.js"></script>


        <script src="static/bootstrap/js/bootstrap.bundle.min.js"></script>

        % if syntax_highlighting:
              <script defer src="static/highlight/highlight.min.js"></script>
          <script>
            window.addEventListener('DOMContentLoaded', () => {
              hljs.highlightAll();
            })
          </script>
        % endif


    </body>
    </html>