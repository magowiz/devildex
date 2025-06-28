<%doc>
    This template overwrites the default rendering of index module,
    using navigation classes of Bootstrap for a clean and integrated look.
</%doc>
<ul class="nav flex-column">
    % for sub_mod in module.submodules():
        <li class="nav-item">
            <a class="nav-link" href="${sub_mod.url(relative_to=module)}">
                <i class="bi bi-folder-fill me-2" style="color: #6c95ba;"></i>
                <span class="text-truncate">${sub_mod.name}</span>
            </a>
        </li>
    % endfor

    % if module.classes() or module.functions() or module.variables():
        <li class="nav-item mt-2">
            <h6 class="nav-link disabled text-uppercase" style="font-size: 0.8rem;">Content</h6>
        </li>
    % endif

    % for cls in module.classes():
        <li class="nav-item">
            <a class="nav-link" href="${cls.url(relative_to=module)}">
                <i class="bi bi-box me-2" style="color: #d9886a;"></i>
                <span class="text-truncate">${cls.name}</span>
            </a>
        </li>
    % endfor

    % for func in module.functions():
        <li class="nav-item">
            <a class="nav-link" href="${func.url(relative_to=module)}">
                <i class="bi bi-gear me-2" style="color: #8cb3d9;"></i>
                <span class="text-truncate">${func.name}</span>
            </a>
        </li>
    % endfor
</ul>