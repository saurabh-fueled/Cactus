#coding:utf-8
import os
import logging
import tempfile
import shutil

from cactus.utils.compat import StaticCompatibilityLayer
from cactus.utils.file import calculate_file_checksum
from cactus.utils.filesystem import alt_file
from cactus.static import optimizers
from cactus.static import processors


class Static(StaticCompatibilityLayer):
    """
    A static resource in the repo
    """

    def __init__(self, site, path):
        self.site = site

        _static_path, filename = os.path.split(path)

        # Actual source file
        self.src_dir = os.path.join('static', _static_path)
        self.src_filename = filename
        self.src_name, self.src_extension = filename.rsplit('.', 1)

        # Useless we'll crash before.
        # TODO
        assert self.src_extension, "No extension for file?! {0}".format(self.src_name)

        # Do some pre-processing (e.g. optimizations):
        # must be done before fingerprinting
        self._preprocessing_path = self.pre_process()

        # Where the file will have to be referenced in output files

        if self.final_extension in self.site.fingerprint_extensions:
            checksum = calculate_file_checksum(self._preprocessing_path)
            new_name = "{0}.{1}".format(self.src_name, checksum)
        else:
            new_name = self.src_name

        # Path where this file should be referenced in source files
        self.link_url = '/' + os.path.join(self.src_dir, '{0}.{1}'.format(self.src_name, self.final_extension))

        self.final_name = "{0}.{1}".format(new_name, self.final_extension)

        # Path where the file should be built to.
        self.build_path = os.path.join(self.src_dir, self.final_name)
        # Path where the file should be referenced in built files
        self.final_url = "/{0}".format(self.build_path)


    @property
    def full_source_path(self):
        return os.path.join(self.site.path, self.src_dir, self.src_filename)

    @property
    def full_build_path(self):
        return os.path.join(self.site.build_path, self.build_path)

    def pre_process(self):
        """
        Does file pre-processing if required
        """
        self.pre_dir = tempfile.mkdtemp()
        pre_path = os.path.join(self.pre_dir, 'file')

        shutil.copy(self.full_source_path, pre_path)

        # Pre-process
        logging.info('Pre-processing: %s' % self.src_name)

        with alt_file(pre_path) as tmp_file:
            for ProcessorClass in processors.processors:
                processor = ProcessorClass(pre_path, tmp_file)
                if self.src_extension in processor.supported_extensions:
                    if processor.run():
                        self.final_extension = processor.output_extension
                        break  # Do not run several processors (Create a new processor for this!)
            else:
                self.final_extension = self.src_extension

        # Optimize
        if self.final_extension in self.site.optimize_extensions:
            with alt_file(pre_path) as tmp_file:
                for OptimizerClass in optimizers.optimizers:
                    optimizer = OptimizerClass(pre_path, tmp_file)
                    if self.final_extension in optimizer.supported_extensions:
                        if optimizer.run():
                            break  # Do not run several optimizers (Create a new optimize for this!)

        return pre_path

    def build(self):
        logging.info('Building {0} --> {1}'.format(self.src_name, self.final_url))

        try:
            os.makedirs(os.path.dirname(self.full_build_path))
        except OSError:
            pass

        copy = lambda: shutil.copy(self._preprocessing_path, self.full_build_path)

        copy()

    def __repr__(self):
        return '<Static: {0}>'.format(self.src_filename)