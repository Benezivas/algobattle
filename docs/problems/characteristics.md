# Basic Requirements
# Basic Requirements for an Algobattle Problem

Before we start to write any code, we discuss which types of problems
are well-suited for the `algobattle` framework, and consequently which types of
problems are not.

Essentially, we are interested in two characteristics, both which revolve around
the solutions of a problem:

1. The solution (a.k.a certificate) of a problem can be verified faster than
   solving the problem itself
2. The verification of a certificate can be done in time at most quadratic in
   the size of the instance.

Both are soft requirements which you can technically ignore. This may, however,
impact your running time significantly. The validation process does not have a
built-in timeout, meaning that if you try to solve an instance during
validation, the framework will not continue until this solution was found or an
error is encountered.

Similarly, if you pose a problem that is easy to solve but costly to verify
(larger than quadratic in the size of the instance), the validation process will
slow down noticeably for higher instance sizes.

There is no restriction on the I/O that problems use. We only enforce all data,
no matter their format, to be passed in the form of files. For a deeper dive
into how to use I/O formats other than `json` files, have a look at the [I/O
Section](io.md).