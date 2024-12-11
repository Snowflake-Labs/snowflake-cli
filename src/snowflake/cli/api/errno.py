# Copyright (c) 2024 Snowflake Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# General errors
NO_WAREHOUSE_SELECTED_IN_SESSION = 606
EMPTY_SQL_STATEMENT = 900

SQL_COMPILATION_ERROR = 1003
OBJECT_ALREADY_EXISTS_IN_DOMAIN = 1998
OBJECT_ALREADY_EXISTS = 2002
DOES_NOT_EXIST_OR_NOT_AUTHORIZED = 2003  # BASE_TABLE_OR_VIEW_NOT_FOUND
DUPLICATE_COLUMN_NAME = 2025
VIEW_EXPANSION_FAILED = 2037
DOES_NOT_EXIST_OR_CANNOT_BE_PERFORMED = (
    2043  # OBJECT_DOES_NOT_EXIST_OR_CANNOT_PERFORM_OPERATION
)
INSUFFICIENT_PRIVILEGES = 3001  # NOT_AUTHORIZED
INVALID_OBJECT_TYPE_FOR_SPECIFIED_PRIVILEGE = 3008
ROLE_NOT_ASSIGNED = 3013
NO_INDIVIDUAL_PRIVS = 3028
OBJECT_ALREADY_EXISTS_NO_PRIVILEGES = 3041

# Native Apps
APPLICATION_PACKAGE_MANIFEST_SPECIFIED_FILE_NOT_FOUND = 93003
APPLICATION_FILE_NOT_FOUND_ON_STAGE = 93009
CANNOT_GRANT_OBJECT_NOT_IN_APP_PACKAGE = 93011
CANNOT_GRANT_RESTRICTED_PRIVILEGE_TO_APP_PACKAGE_SHARE = 93012
APPLICATION_PACKAGE_VERSION_ALREADY_EXISTS = 93030
APPLICATION_PACKAGE_VERSION_NAME_TOO_LONG = 93035
APPLICATION_PACKAGE_PATCH_DOES_NOT_EXIST = 93036
APPLICATION_PACKAGE_MAX_VERSIONS_HIT = 93037
CANNOT_UPGRADE_FROM_LOOSE_FILES_TO_VERSION = 93044
CANNOT_UPGRADE_FROM_VERSION_TO_LOOSE_FILES = 93045
ONLY_SUPPORTED_ON_DEV_MODE_APPLICATIONS = 93046
NO_VERSIONS_AVAILABLE_FOR_ACCOUNT = 93054
NOT_SUPPORTED_ON_DEV_MODE_APPLICATIONS = 93055
APPLICATION_NO_LONGER_AVAILABLE = 93079
APPLICATION_INSTANCE_FAILED_TO_RUN_SETUP_SCRIPT = 93082
APPLICATION_INSTANCE_NO_ACTIVE_WAREHOUSE_FOR_CREATE_OR_UPGRADE = 93083
APPLICATION_INSTANCE_EMPTY_SETUP_SCRIPT = 93084
APPLICATION_PACKAGE_CANNOT_DROP_VERSION_IF_IT_IS_IN_USE = 93088
APPLICATION_PACKAGE_MANIFEST_CONTAINER_IMAGE_URL_BAD_VALUE = 93148
CANNOT_GRANT_NON_MANIFEST_PRIVILEGE = 93118
APPLICATION_OWNS_EXTERNAL_OBJECTS = 93128
APPLICATION_PACKAGE_PATCH_ALREADY_EXISTS = 93168
APPLICATION_PACKAGE_CANNOT_SET_EXTERNAL_DISTRIBUTION_WITH_SPCS = 93197
NATIVE_APPLICATION_MANIFEST_UNRECOGNIZED_FIELD = 93301
NATIVE_APPLICATION_MANIFEST_UNEXPECTED_VALUE_FOR_PROPERTY = 93302
NATIVE_APPLICATION_MANIFEST_GENERIC_JSON_ERROR = 93303
NATIVE_APPLICATION_MANIFEST_INVALID_SYNTAX = 93300
APPLICATION_REQUIRES_TELEMETRY_SHARING = 93321
CANNOT_DISABLE_MANDATORY_TELEMETRY = 93329
VERSION_NOT_ADDED_TO_RELEASE_CHANNEL = 512008
CANNOT_DISABLE_RELEASE_CHANNELS = 512001
RELEASE_DIRECTIVES_VERSION_PATCH_NOT_FOUND = 93036
RELEASE_DIRECTIVE_DOES_NOT_EXIST = 93090
VERSION_DOES_NOT_EXIST = 93031
ACCOUNT_DOES_NOT_EXIST = 1999
ACCOUNT_HAS_TOO_MANY_QUALIFIERS = 906

ERR_JAVASCRIPT_EXECUTION = 100132

SNOWSERVICES_IMAGE_REPOSITORY_IMAGE_IMPORT_TO_NATIVE_APP_FAIL = 397007
SNOWSERVICES_IMAGE_MANIFEST_NOT_FOUND = 397012
SNOWSERVICES_IMAGE_REPOSITORY_FAILS_TO_RETRIEVE_IMAGE_HASH_NEW = 397013

NO_REFERENCE_SET_FOR_DEFINITION = 505019
NO_ACTIVE_REF_DEFINITION_WITH_REF_NAME_IN_APPLICATION = 505026
