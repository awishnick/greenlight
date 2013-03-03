angular.module('greenlightServices', ['ngResource'])
    .factory('Project', function($resource) {
        return $resource('/api/projects/:projectId', {}, {
            query: {
                method: 'GET',
                isArray: false
            }
        });
    });

angular.module('greenlight', ['greenlightServices'])
    .config(['$routeProvider', function($routeProvider) {
        $routeProvider
            .when('/projects', {
                templateUrl: 'templates/project-list.html',
                controller: ProjectListCtrl
            })
            .when('/projects/:projectId', {
                templateUrl: 'templates/project-detail.html',
                controller: ProjectDetailCtrl
            })
            .otherwise({redirectTo: '/projects'});
    }])
    .directive('spinner', function() {
        return {
            restrict: 'E',
            replace: true,
            transclude: true,
            template: '<div ng-transclude style="margin: 10px 10px 10px 10px;"></div>',
            link: function(scope, element, attrs) {
                var opts = {

                }
                var opts = {
                    lines: 13, // The number of lines to draw
                    length: 4, // The length of each line
                    width: 2, // The line thickness
                    radius: 5, // The radius of the inner circle
                    corners: 1, // Corner roundness (0..1)
                };
                var spinner = new Spinner(opts).spin();
                element.append(spinner.el);
            }
        }
    })
    .directive('spinnerBig', function() {
        return {
            restrict: 'E',
            replace: true,
            transclude: true,
            template: '<div ng-transclude style="width: 24px; height: 24px; margin: 24px; 0 0 24px;"></div>',
            link: function(scope, element, attrs) {
                var opts = {

                }
                var opts = {
                    lines: 13, // The number of lines to draw
                    length: 7, // The length of each line
                    width: 4, // The line thickness
                    radius: 10, // The radius of the inner circle
                    corners: 1, // Corner roundness (0..1)
                };
                var spinner = new Spinner(opts).spin();
                element.append(spinner.el);
            }
        }
    })
    ;

function installProjectHelpers($scope) {
    $scope.isProjectSuccess = function(project) {
        return project.returncode == 0;
    }

    $scope.isProjectFailure = function(project) {
        return project.returncode != 0 &&
               project.returncode != null &&
               project.mtime != null;
    }

    $scope.isProjectNeverRun = function(project) {
        return project.mtime == null ||
               project.returncode == null;
    }

    // Should the spinner be shown?
    $scope.isProjectBeingRun = function(project) {
        return !project.up_to_date &&
               project.mtime;
    }
}

function projectHasChanged(old_project, new_project) {
    if (new_project.up_to_date != old_project.up_to_date) {
        return true;
    }
    if (new_project.returncode != old_project.returncode) {
        return true;
    }
    if (new_project.mtime != old_project.mtime) {
        return true;
    }

    return false;
}

function ProjectListCtrl($scope, $timeout, Project) {
    installProjectHelpers($scope);
    $scope.projects = Project.query();

    function updateTimer() {
        $timeout(function() {
            var update = Project.query(function() {
                do_update = false;
                for (i in update) {
                    if (!update.hasOwnProperty(i)) {
                        continue;
                    }
                    if (!(i in $scope.projects)) {
                        do_update = true;
                        break;
                    }

                    if (projectHasChanged($scope.projects[i], update[i])) {
                        do_update = true;
                    }
                }

                if (do_update) {
                    $scope.projects = update;
                }
            });
            updateTimer();
        }, 1000);
    };


    updateTimer();
}

function ProjectDetailCtrl($scope, $routeParams, $timeout, Project) {
    installProjectHelpers($scope);
    $scope.project = Project.get({projectId: $routeParams.projectId});

    function updateTimer() {
        $timeout(function() {
            var new_project = Project.get({projectId: $routeParams.projectId},
                                          function() {
                if (projectHasChanged($scope.project, new_project)) {
                    $scope.project = new_project;
                }
            });

            updateTimer();
        }, 1000);
    };

    updateTimer();
}
