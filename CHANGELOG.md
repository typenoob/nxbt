## Description

For those who have trouble in installing this application, I added dockerfile and built executable binary files in order to easily install on multiple platforms.

You can simply download executable files in [release](https://github.com/typenoob/nxbt/releases).

Requirements:
- Tag glib is for gnu based libc platform with glibc>=2.28
- Tag musl is for musl based libc platform with musl-libc>=1.2.2

Use following command to build your own image.

``` docker build -t  [TAG_NAME] -f docker/[LIBC_KIND]/Dockerfile . ```

You can use built image from [here](https://hub.docker.com/r/typenoob/nxbt) as well.
